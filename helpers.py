import os
import time
import requests
import kubernetes
from packaging import version

# Used below in init variables
def detectPrometheusURL():

    # Method #1: Use env vars which are set when run in the same namespace as prometheus
    prometheus_ip_address = os.getenv('PROMETHEUS_SERVER_SERVICE_HOST')
    prometheus_port = os.getenv('PROMETHEUS_SERVER_SERVICE_PORT_HTTP')

    # TODO: If there's other ways to also detect prometheus (eg: try http://prometheus-server) please put them here...

    if not prometheus_ip_address or not prometheus_port:
        print("ERROR: PROMETHEUS_URL was not set, and can not auto-detect where prometheus is")
        exit(-1)
    return "http://{}:{}".format(prometheus_ip_address,prometheus_port)

# Input/configuration variables
INTERVAL_TIME = int(os.getenv('INTERVAL_TIME') or 60)                               # How often (in seconds) to scan prometheus for checking if we need to resize
SCALE_ABOVE_PERCENT = int(os.getenv('SCALE_ABOVE_PERCENT') or 80)                   # What percent out of 100 the volume must be consuming before considering to scale it
SCALE_AFTER_INTERVALS = int(os.getenv('SCALE_AFTER_INTERVALS') or 5)                # How many intervals of INTERVAL_TIME a volume must be above SCALE_ABOVE_PERCENT before we scale
SCALE_UP_PERCENT = int(os.getenv('SCALE_UP_PERCENT') or 50)                         # How much percent of the current volume size to scale up by.  eg: 100 == (if disk is 10GB, scale to 20GB), eg: 50 == (if disk is 10GB, scale to 15GB)
SCALE_UP_MIN_INCREMENT = int(os.getenv('SCALE_UP_MIN_INCREMENT') or 1000000000)     # How many bytes is the minimum that we can resize up by, default is 1GB (in bytes, so 1000000000)
SCALE_UP_MAX_INCREMENT = int(os.getenv('SCALE_UP_MAX_INCREMENT') or 16000000000000) # How many bytes is the maximum that we can resize up by, default is 16TB (in bytes, so 16000000000000)
SCALE_UP_MAX_SIZE = int(os.getenv('SCALE_UP_MAX_SIZE') or 16000000000000)           # How many bytes is the maximum disk size that we can resize up, default is 16TB for EBS volumes in AWS (in bytes, so 16000000000000)
SCALE_COOLDOWN_TIME = int(os.getenv('SCALE_COOLDOWN_TIME') or 22200)                # How long (in seconds) we must wait before scaling this volume again.  For AWS EBS, this is 6 hours which is 21600 seconds but for good measure we add an extra 10 minutes to this, so 22200
PROMETHEUS_URL = os.getenv('PROMETHEUS_URL') or detectPrometheusURL()               # Where prometheus is, if not provided it can auto-detect it if it's in the same namespace as us
DRY_RUN = True if os.getenv('DRY_RUN', False) else False                            # If we want to dry-run this
PROMETHEUS_LABEL_MATCH = os.getenv('PROMETHEUS_LABEL_MATCH') or ''                  # A PromQL label query to restrict volumes for this to see and scale, without braces.  eg: 'namespace="dev"'
HTTP_TIMEOUT = os.getenv('HTTP_TIMEOUT') or 15                                      # Allows to set the timeout for calls to Prometheus and Kubernetes.  This might be needed if your Prometheus or Kubernetes is over a remote WAN link with high latency and/or is heavily loaded
PROMETHEUS_VERSION = "Unknown"                                                      # Uses to detect the availability of a new function called present_over_time only available on Prometheus v2.30.0 or newer, this is auto-detected and updated, not set by a user


#############################
# Initialize Kubernetes
#############################
try:
    # First, try to use in-cluster config, aka run inside of Kubernetes
    kubernetes.config.load_incluster_config()
except Exception as e:
    try:
        # If we aren't running in kubernetes, try to use the kubectl config file as a fallback
        kubernetes.config.load_kube_config()
    except Exception as ex:
        raise ex
kubernetes_core_api  = kubernetes.client.CoreV1Api()


#############################
# Helper functions
#############################
# Simple header printing before the program starts, prints the variables this is configured for at runtime
def printHeaderAndConfiguration():
    print("---------------------------------------------------------------")
    print("               Volume Autoscaler - Configuration               ")
    print("---------------------------------------------------------------")
    print("             Prometheus URL: {}".format(PROMETHEUS_URL))
    print("         Prometheus Version: {}".format(PROMETHEUS_VERSION))
    print("          Prometheus Labels: {{{}}}".format(PROMETHEUS_LABEL_MATCH))
    print("    Interval to query usage: every {} seconds".format(INTERVAL_TIME))
    print("             Scale up after: {} intervals ({} seconds total)".format(SCALE_AFTER_INTERVALS, SCALE_AFTER_INTERVALS * INTERVAL_TIME))
    print("     Scale above percentage: disk is over {}% full".format(SCALE_ABOVE_PERCENT))
    print(" Scale up minimum increment: {} bytes, or {}".format(SCALE_UP_MIN_INCREMENT, convert_bytes_to_storage(SCALE_UP_MIN_INCREMENT)))
    print(" Scale up maximum increment: {} bytes, or {}".format(SCALE_UP_MAX_INCREMENT, convert_bytes_to_storage(SCALE_UP_MAX_INCREMENT)))
    print("      Scale up maximum size: {} bytes, or {}".format(SCALE_UP_MAX_SIZE, convert_bytes_to_storage(SCALE_UP_MAX_SIZE)))
    print("        Scale up percentage: {}% of current disk size".format(SCALE_UP_PERCENT))
    print("          Scale up cooldown: only resize every {} seconds".format(SCALE_COOLDOWN_TIME))
    print("                    Dry Run: is {}".format("ENABLED, no scaling will occur!" if DRY_RUN else "Disabled"))
    print("---------------------------------------------------------------")


# Figure out how many bytes to scale to based on the original size, scale up percent, minimum increment and maximum size
def calculateBytesToScaleTo(original_size, scale_up_percent, min_increment, max_increment, maximum_size):
    try:
        resize_to_bytes = int((original_size * (0.01 * scale_up_percent)) + original_size)
        # Check if resize bump is too small
        if resize_to_bytes - original_size < min_increment:
            # Using default scale up if too small
            resize_to_bytes = original_size + min_increment

        # Check if resize bump is too large
        if resize_to_bytes - original_size > max_increment:
            # Using default scale up if too large
            resize_to_bytes = original_size + max_increment

        # Now check if it is too large overall (max disk size)
        if resize_to_bytes > maximum_size:
            resize_to_bytes = maximum_size

        # Now check if we're already maxed (16TB?) then we don't need to complete this scale activity
        if original_size == resize_to_bytes:
            return False

        # If we're good, send back our resizeto byets
        return resize_to_bytes
    except Exception as e:
        print("Exception, unable to calculate bytes to scale to: ")
        print(e)
        return False


# Convert the K8s storage size definitions (eg: 10G, 5Ti, etc) into number of bytes
def convert_storage_to_bytes(storage):

    # BinarySI == Ki | Mi | Gi | Ti | Pi | Ei
    if storage.endswith('Ki'):
        return int(storage.replace("Ki","")) * 1024
    if storage.endswith('Mi'):
        return int(storage.replace("Mi","")) * 1024 * 1024
    if storage.endswith('Gi'):
        return int(storage.replace("Gi","")) * 1024 * 1024 * 1024
    if storage.endswith('Ti'):
        return int(storage.replace("Ti","")) * 1024 * 1024 * 1024 * 1024
    if storage.endswith('Pi'):
        return int(storage.replace("Pi","")) * 1024 * 1024 * 1024 * 1024 * 1024
    if storage.endswith('Ei'):
        return int(storage.replace("Ei","")) * 1024 * 1024 * 1024 * 1024 * 1024 * 1024

    # decimalSI == m | k | M | G | T | P | E | "" (this last one is the fallthrough at the end)
    if storage.endswith('k'):
        return int(storage.replace("k","")) * 1000
    if storage.endswith('K'):
        return int(storage.replace("K","")) * 1000
    if storage.endswith('m'):
        return int(storage.replace("m","")) * 1000 * 1000
    if storage.endswith('M'):
        return int(storage.replace("M","")) * 1000 * 1000
    if storage.endswith('G'):
        return int(storage.replace("G","")) * 1000 * 1000 * 1000
    if storage.endswith('T'):
        return int(storage.replace("T","")) * 1000 * 1000 * 1000 * 1000
    if storage.endswith('P'):
        return int(storage.replace("P","")) * 1000 * 1000 * 1000 * 1000 * 1000
    if storage.endswith('E'):
        return int(storage.replace("E","")) * 1000 * 1000 * 1000 * 1000 * 1000 * 1000

    # decimalExponent == e | E (in the middle of two integers)
    lowercaseDecimalExponent = storage.split('e')
    uppercaseDecimalExponent = storage.split('E')
    if len(lowercaseDecimalExponent) > 1 or len(uppercaseDecimalExponent) > 1:
        return int(float(str(format(float(storage)))))

    # If none above match, then it should just be an integer value (in bytes)
    return int(storage)


# Try a numeric format to see if it's close enough (within 10 percent, aka 0.1) to the definition
def try_numeric_format(bytes, size_multiplier, suffix, match_by_percentage = 0.1):
    # If bytes is too small, right away exit
    if bytes < (size_multiplier - (size_multiplier * match_by_percentage)):
        return False
    try_result = round(bytes / size_multiplier)
    # print("try_result = {}".format(try_result))
    retest_value = try_result * size_multiplier
    # print("retest_value = {}".format(retest_value))
    difference = abs(retest_value - bytes)
    # print("difference = {}".format(difference))
    if difference < (bytes * 0.1):
        return "{}{}".format(try_result, suffix)
    return False


# Convert bytes (int) to an "sexY" kubernetes storage definition (10G, 5Ti, etc)
# TODO?: If possible, add hinting of which to try first, base10 or base2, based on what was used previously to get closer to the right amount
def convert_bytes_to_storage(bytes):

    # Todo: Add Petabytes/Exobytes?

    # First, we'll try all base10 values...
    # Check if we can convert this into terrabytes
    result = try_numeric_format(bytes, 1000000000000, 'T')
    if result:
        return result

    # Check if we can convert this into gigabytes
    result = try_numeric_format(bytes, 1000000000, 'G')
    if result:
        return result

    # Check if we can convert this into megabytes
    result = try_numeric_format(bytes, 1000000, 'M')
    if result:
        return result

    # Do we ever use things this small?  For now going to skip this...
    # result = try_numeric_format(bytes, 1000, 'k')
    # if result:
    #     return result

    # Next, we'll try all base2 values...
    result = try_numeric_format(bytes, 1099511627776, 'Ti')
    if result:
        return result

    # Next, we'll try all base2 values...
    result = try_numeric_format(bytes, 1073741824, 'Gi')
    if result:
        return result

    # Next, we'll try all base2 values...
    result = try_numeric_format(bytes, 1048576, 'Mi')
    if result:
        return result

    # # Do we ever use things this small?  For now going to skip this...
    # result = try_numeric_format(bytes, 1024, 'Ki')
    # if result:
    #     return result

    # Worst-case just return bytes, a non-sexy value
    return bytes


# The PVC definition from Kubernetes has tons of variables in various maps of maps of maps, simplify
# it to a flat dict for the values we care about, along with allowing per-pvc overrides from annotations
def convert_pvc_to_simpler_dict(pvc):
    return_dict = {}
    return_dict['name'] = pvc.metadata.name
    try:
        return_dict['volume_size_spec'] = pvc.spec.resources.requests['storage']
    except:
        return_dict['volume_size_spec'] = "0"
    return_dict['volume_size_spec_bytes'] = convert_storage_to_bytes(return_dict['volume_size_spec'])
    try:
        return_dict['volume_size_status'] = pvc.status.capacity['storage']
    except:
        return_dict['volume_size_status'] = "0"
    return_dict['volume_size_status_bytes'] = convert_storage_to_bytes(return_dict['volume_size_status'])
    return_dict['namespace'] = pvc.metadata.namespace
    try:
        return_dict['storage_class'] = pvc.spec.storage_class_name
    except:
        return_dict['storage_class'] = ""

    # Set our defaults
    return_dict['last_resized_at']        = 0
    return_dict['scale_above_percent']    = SCALE_ABOVE_PERCENT
    return_dict['scale_after_intervals']  = SCALE_AFTER_INTERVALS
    return_dict['scale_up_percent']       = SCALE_UP_PERCENT
    return_dict['scale_up_min_increment'] = SCALE_UP_MIN_INCREMENT
    return_dict['scale_up_max_increment'] = SCALE_UP_MAX_INCREMENT
    return_dict['scale_up_max_size']      = SCALE_UP_MAX_SIZE
    return_dict['scale_cooldown_time']    = SCALE_COOLDOWN_TIME
    return_dict['ignore']                 = False

    # Override defaults with annotations on the PVC
    if 'volume.autoscaler.kubernetes.io/last-resized-at' in pvc.metadata.annotations:
        return_dict['last_resized_at'] = int(pvc.metadata.annotations['volume.autoscaler.kubernetes.io/last-resized-at'])
    if 'volume.autoscaler.kubernetes.io/scale-above-percent' in pvc.metadata.annotations:
        return_dict['scale_above_percent'] = int(pvc.metadata.annotations['volume.autoscaler.kubernetes.io/scale-above-percent'])
    if 'volume.autoscaler.kubernetes.io/scale-after-intervals' in pvc.metadata.annotations:
        return_dict['scale_after_intervals'] = int(pvc.metadata.annotations['volume.autoscaler.kubernetes.io/scale-after-intervals'])
    if 'volume.autoscaler.kubernetes.io/scale-up-percent' in pvc.metadata.annotations:
        return_dict['scale_up_percent'] = int(pvc.metadata.annotations['volume.autoscaler.kubernetes.io/scale-up-percent'])
    if 'volume.autoscaler.kubernetes.io/scale-up-min-increment' in pvc.metadata.annotations:
        return_dict['scale_up_min_increment'] = int(pvc.metadata.annotations['volume.autoscaler.kubernetes.io/scale-up-min-increment'])
    if 'volume.autoscaler.kubernetes.io/scale-up-max-increment' in pvc.metadata.annotations:
        return_dict['scale_up_max_increment'] = int(pvc.metadata.annotations['volume.autoscaler.kubernetes.io/scale-up-max-increment'])
    if 'volume.autoscaler.kubernetes.io/scale-up-max-size' in pvc.metadata.annotations:
        return_dict['scale_up_max_size'] = int(pvc.metadata.annotations['volume.autoscaler.kubernetes.io/scale-up-max-size'])
    if 'volume.autoscaler.kubernetes.io/scale-cooldown-time' in pvc.metadata.annotations:
        return_dict['scale_cooldown_time'] = int(pvc.metadata.annotations['volume.autoscaler.kubernetes.io/scale-cooldown-time'])
    if 'volume.autoscaler.kubernetes.io/ignore' in pvc.metadata.annotations and pvc.metadata.annotations['volume.autoscaler.kubernetes.io/ignore'].lower() == "true":
        return_dict['ignore'] = True

    # Return our cleaned up and simple flat dict with the values we care about, with overrides if specified
    return return_dict


# Describe all the PVCs in Kubernetes
# TODO: Check if we need to page this, and how well it handles scale (100+ PVCs, etc)
def describe_all_pvcs(simple=False):
    api_response = kubernetes_core_api.list_persistent_volume_claim_for_all_namespaces(timeout_seconds=HTTP_TIMEOUT)
    output_objects = {}
    for item in api_response.items:
        if simple:
            output_objects["{}.{}".format(item.metadata.namespace,item.metadata.name)] = convert_pvc_to_simpler_dict(item)
        else:
            output_objects["{}.{}".format(item.metadata.namespace,item.metadata.name)] = item

    return output_objects


# Scale up an PVC in Kubernetes
def scale_up_pvc(namespace, name, new_size):
    try:
        result = kubernetes_core_api.patch_namespaced_persistent_volume_claim(
                    name=name,
                    namespace=namespace,
                    body={
                        "metadata": {"annotations": {"volume.autoscaler.kubernetes.io/last-resized-at": str(int(time.mktime(time.gmtime())))}},
                        "spec": {"resources": {"requests": {"storage": new_size}} }
                    }
                )

        print("  Desired New Size: {}".format(new_size))
        print("  Actual New Size: {}".format(convert_storage_to_bytes(result.spec.resources.requests['storage'])))

        # If the new size is within' 10% of the desired size.  This is necessary because of the megabyte/mebibyte issue
        if abs(convert_storage_to_bytes(result.spec.resources.requests['storage']) - new_size) < (new_size * 0.1):
            return result
        else:
            raise Exception("  New size did not take for some reason")

        return result
    except Exception as e:
        print("  Exception raised while trying to scale up PVC {}.{} to {} ...".format(namespace, name, new_size))
        print(e)
        return False

# Test if prometheus is accessible, and gets the build version so we know which function(s) are available or not, primarily for present_over_time below
def testIfPrometheusIsAccessible(url):
    global PROMETHEUS_VERSION
    try:
        response = requests.get(url + '/api/v1/status/buildinfo', timeout=HTTP_TIMEOUT)
        if response.status_code != 200:
            raise Exception("ERROR: Received status code {} while trying to initialize on Prometheus: {}".format(response.status_code, url))
        response_object = response.json()
        PROMETHEUS_VERSION = response_object['data']['version']
    except Exception as e:
        print(e)
        exit(-1)

# Get a list of PVCs from Prometheus with their metrics of disk usage
def fetch_pvcs_from_prometheus(url, label_match):
    print("Querying prometheus...")
    # This only works on Prometheus v2.30.0 or newer, using this helps prevent false-negatives
    if version.parse(PROMETHEUS_VERSION) >= version.parse("2.30.0"):
        response = requests.get(url + '/api/v1/query', params={'query': "ceil((1 - kubelet_volume_stats_available_bytes{{ {} }} / kubelet_volume_stats_capacity_bytes)*100) and present_over_time(kubelet_volume_stats_available_bytes{{ {} }}[1h])".format(label_match,label_match)}, timeout=HTTP_TIMEOUT)
    else:
        response = requests.get(url + '/api/v1/query', params={'query': "ceil((1 - kubelet_volume_stats_available_bytes{{ {} }} / kubelet_volume_stats_capacity_bytes)*100)".format(label_match,label_match)}, timeout=HTTP_TIMEOUT)

    response_object = response.json()

    if response_object['status'] != 'success':
        print("Prometheus query failed with code: {}".format(response_object['status']))
        if 'error' in response_object:
            print("Prometheus Error: {}".format(response_object['error']))
            exit(-1)

    return response_object['data']['result']





# Unused at the moment
# def describe_pvc(namespace, name, simple=False):
#     api_response = kubernetes_core_api.list_namespaced_persistent_volume_claim(namespace, limit=1, field_selector="metadata.name=" + name, timeout_seconds=HTTP_TIMEOUT)
#     # print(api_response)
#     for item in api_response.items:
#         # If the user wants pre-parsed, making it a bit easier to work with than a huge map of map of maps
#         if simple:
#             return convert_pvc_to_simpler_dict(item)
#         return item
