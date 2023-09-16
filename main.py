#!/usr/bin/env python3
import os
import time
from helpers import INTERVAL_TIME, PROMETHEUS_URL, DRY_RUN, VERBOSE, get_settings_for_prometheus_metrics, is_integer_or_float, print_human_readable_volume_dict
from helpers import convert_bytes_to_storage, scale_up_pvc, testIfPrometheusIsAccessible, describe_all_pvcs, send_kubernetes_event
from helpers import fetch_pvcs_from_prometheus, printHeaderAndConfiguration, calculateBytesToScaleTo, GracefulKiller
from prometheus_client import start_http_server, Summary, Gauge, Counter, Info
import slack
import sys, traceback

# Initialize our Prometheus metrics (counters)
PROMETHEUS_METRICS = {}
PROMETHEUS_METRICS['resize_evaluated']  = Counter('volume_autoscaler_resize_evaluated',  'Counter which is increased every time we evaluate resizing PVCs')
PROMETHEUS_METRICS['resize_attempted']  = Counter('volume_autoscaler_resize_attempted',  'Counter which is increased every time we attempt to resize')
PROMETHEUS_METRICS['resize_successful'] = Counter('volume_autoscaler_resize_successful', 'Counter which is increased every time we successfully resize')
PROMETHEUS_METRICS['resize_failure']    = Counter('volume_autoscaler_resize_failure',    'Counter which is increased every time we fail to resize')
# Initialize our Prometheus metrics (gauges)
PROMETHEUS_METRICS['num_valid_pvcs'] = Gauge('volume_autoscaler_num_valid_pvcs', 'Gauge with the number of valid PVCs detected which we found to consider for scaling')
PROMETHEUS_METRICS['num_valid_pvcs'].set(0)
PROMETHEUS_METRICS['num_pvcs_above_threshold'] = Gauge('volume_autoscaler_num_pvcs_above_threshold', 'Gauge with the number of PVCs detected above the desired percentage threshold')
PROMETHEUS_METRICS['num_pvcs_above_threshold'].set(0)
PROMETHEUS_METRICS['num_pvcs_below_threshold'] = Gauge('volume_autoscaler_num_pvcs_below_threshold', 'Gauge with the number of PVCs detected below the desired percentage threshold')
PROMETHEUS_METRICS['num_pvcs_below_threshold'].set(0)
# Initialize our Prometheus metrics (info/settings)
PROMETHEUS_METRICS['info'] = Info('volume_autoscaler_release', 'Release/version information about this volume autoscaler service')
PROMETHEUS_METRICS['info'].info({'version': '1.0.5'})
PROMETHEUS_METRICS['settings'] = Info('volume_autoscaler_settings', 'Settings currently used in this service')
PROMETHEUS_METRICS['settings'].info(get_settings_for_prometheus_metrics())

# Other globals
IN_MEMORY_STORAGE = {}
MAIN_LOOP_TIME = 1

# Entry point and main application loop
if __name__ == "__main__":

    # Test if our prometheus URL works before continuing
    testIfPrometheusIsAccessible(PROMETHEUS_URL)

    # Startup our prometheus metrics endpoint
    start_http_server(8000)

    # TODO: Test k8s access, or just test on-the-fly below?

    # Reporting our configuration to the end-user
    printHeaderAndConfiguration()

    # Setup our graceful handling of kubernetes signals
    killer = GracefulKiller()
    last_run = 0

    # Our main run loop, now using a signal handler to handle kubernetes signals gracefully (not mid-loop)
    while not killer.kill_now:

        # If it's not our interval time yet, only run once every INTERVAL_TIME seconds.  This extra bit helps us handle signals gracefully quicker
        if int(time.time()) - last_run <= INTERVAL_TIME:
            time.sleep(MAIN_LOOP_TIME)
            continue
        last_run = int(time.time())

        # In every loop, fetch all our pvcs state from Kubernetes
        try:
            PROMETHEUS_METRICS['resize_evaluated'].inc()
            pvcs_in_kubernetes = describe_all_pvcs(simple=True)
        except Exception:
            print("Exception while trying to describe all PVCs")
            traceback.print_exc()
            time.sleep(MAIN_LOOP_TIME)
            continue

        # Fetch our volume usage from Prometheus
        try:
            pvcs_in_prometheus = fetch_pvcs_from_prometheus(url=PROMETHEUS_URL)
            print("Querying and found {} valid PVCs to assess in prometheus".format(len(pvcs_in_prometheus)))
            PROMETHEUS_METRICS['num_valid_pvcs'].set(len(pvcs_in_prometheus))
        except Exception:
            print("Exception while trying to fetch PVC metrics from prometheus")
            traceback.print_exc()
            time.sleep(MAIN_LOOP_TIME)
            continue

        # Iterate through every item and handle it accordingly
        PROMETHEUS_METRICS['num_pvcs_above_threshold'].set(0)  # Reset these each loop
        PROMETHEUS_METRICS['num_pvcs_below_threshold'].set(0)  # Reset these each loop
        for item in pvcs_in_prometheus:
            try:
                volume_name = str(item['metric']['persistentvolumeclaim'])
                volume_namespace = str(item['metric']['namespace'])
                volume_description = "{}.{}".format(item['metric']['namespace'], item['metric']['persistentvolumeclaim'])
                volume_used_percent = int(item['value'][1])

                # Precursor check to ensure we have info for this pvc in kubernetes object
                if volume_description not in pvcs_in_kubernetes:
                    print("ERROR: The volume {} was not found in Kubernetes but had metrics in Prometheus.  This may be an old volume, was just deleted, or some random jitter is occurring.  If this continues to occur, please report an bug.  You might also be using an older version of Prometheus, please make sure you're using v2.30.0 or newer before reporting a bug for this.".format(volume_description))
                    continue

                if VERBOSE:
                    print("Volume {} is {}% in-use of the {} available".format(volume_description,volume_used_percent,pvcs_in_kubernetes[volume_description]['volume_size_status']))
                    print("  VERBOSE DETAILS:")
                    print("-------------------------------------------------------------------------------------------------------------")
                    print_human_readable_volume_dict(pvcs_in_kubernetes[volume_description])
                    print("-------------------------------------------------------------------------------------------------------------")

                # Check if we are NOT in an alert condition
                if volume_used_percent < pvcs_in_kubernetes[volume_description]['scale_above_percent']:
                    PROMETHEUS_METRICS['num_pvcs_below_threshold'].inc()
                    if volume_description in IN_MEMORY_STORAGE:
                        del IN_MEMORY_STORAGE[volume_description]
                    if VERBOSE:
                        print(" and is not above {}%".format(pvcs_in_kubernetes[volume_description]['scale_above_percent']))
                    continue
                else:
                    PROMETHEUS_METRICS['num_pvcs_above_threshold'].inc()

                # If we are in alert condition, record this in our simple in-memory counter
                if volume_description in IN_MEMORY_STORAGE:
                    IN_MEMORY_STORAGE[volume_description] = IN_MEMORY_STORAGE[volume_description] + 1
                else:
                    IN_MEMORY_STORAGE[volume_description] = 1
                # Incase we aren't verbose, and didn't print this above, now that we're in alert we will print this
                if not VERBOSE:
                    print("Volume {} is {}% in-use of the {} available".format(volume_description,volume_used_percent,pvcs_in_kubernetes[volume_description]['volume_size_status']))
                # Print the alert status
                print("  BECAUSE it is above {}% used".format(pvcs_in_kubernetes[volume_description]['scale_above_percent']))
                print("  ALERT has been for {} period(s) which needs to at least {} period(s) to scale".format(IN_MEMORY_STORAGE[volume_description], pvcs_in_kubernetes[volume_description]['scale_after_intervals']))

                # Check if we are NOT in a possible scale condition
                if IN_MEMORY_STORAGE[volume_description] < pvcs_in_kubernetes[volume_description]['scale_after_intervals']:
                    print("  BUT need to wait for {} intervals in alert before considering to scale".format( pvcs_in_kubernetes[volume_description]['scale_after_intervals'] ))
                    print("  FYI this has desired_size {} and current size {}".format( convert_bytes_to_storage(pvcs_in_kubernetes[volume_description]['volume_size_spec_bytes']), convert_bytes_to_storage(pvcs_in_kubernetes[volume_description]['volume_size_status_bytes'])))
                    continue

                # If we are in a possible scale condition, check if we recently scaled it and handle accordingly
                if pvcs_in_kubernetes[volume_description]['last_resized_at'] + pvcs_in_kubernetes[volume_description]['scale_cooldown_time'] >= int(time.mktime(time.gmtime())):
                    print("  BUT need to wait {} seconds to scale since the last scale time {} seconds ago".format( abs(pvcs_in_kubernetes[volume_description]['last_resized_at'] + pvcs_in_kubernetes[volume_description]['scale_cooldown_time']) - int(time.mktime(time.gmtime())), abs(pvcs_in_kubernetes[volume_description]['last_resized_at'] - int(time.mktime(time.gmtime()))) ))
                    continue

                # If we reach this far then we will be scaling the disk, all preconditions were passed from above
                if pvcs_in_kubernetes[volume_description]['last_resized_at'] == 0:
                    print("  AND we need to scale it immediately, it has never been scaled previously")
                else:
                    print("  AND we need to scale it immediately, it last scaled {} seconds ago".format( abs((pvcs_in_kubernetes[volume_description]['last_resized_at'] + pvcs_in_kubernetes[volume_description]['scale_cooldown_time']) - int(time.mktime(time.gmtime()))) ))

                # Calculate how many bytes to resize to based on the parameters provided globally and per-this pv annotations
                resize_to_bytes = calculateBytesToScaleTo(
                    original_size     = pvcs_in_kubernetes[volume_description]['volume_size_status_bytes'],
                    scale_up_percent  = pvcs_in_kubernetes[volume_description]['scale_up_percent'],
                    min_increment     = pvcs_in_kubernetes[volume_description]['scale_up_min_increment'],
                    max_increment     = pvcs_in_kubernetes[volume_description]['scale_up_max_increment'],
                    maximum_size      = pvcs_in_kubernetes[volume_description]['scale_up_max_size'],
                )
                # TODO: Check here if storage class has the ALLOWVOLUMEEXPANSION flag set to true, read the SC from pvcs_in_kubernetes[volume_description]['storage_class'] ?

                # If our resize bytes failed for some reason, eg putting invalid data into the annotations on the PV
                if resize_to_bytes == False:
                    print("-------------------------------------------------------------------------------------------------------------")
                    print("  Error/Exception while trying to determine what to resize to, volume causing failure:")
                    print("-------------------------------------------------------------------------------------------------------------")
                    print(pvcs_in_kubernetes[volume_description])
                    print("-------------------------------------------------------------------------------------------------------------")
                    continue

                # If our resize bytes is less than our original size (because the user set the max-bytes to something too low)
                if resize_to_bytes < pvcs_in_kubernetes[volume_description]['volume_size_status_bytes']:
                    print("-------------------------------------------------------------------------------------------------------------")
                    print("  Error/Exception while trying to scale this up.  Is it possible your maximum SCALE_UP_MAX_SIZE is too small?")
                    print("-------------------------------------------------------------------------------------------------------------")
                    print("   Maximum Size: {} ({})".format(pvcs_in_kubernetes[volume_description]['scale_up_max_size'], convert_bytes_to_storage(pvcs_in_kubernetes[volume_description]['scale_up_max_size'])))
                    print("  Original Size: {} ({})".format(pvcs_in_kubernetes[volume_description]['volume_size_status_bytes'], convert_bytes_to_storage(pvcs_in_kubernetes[volume_description]['volume_size_status_bytes'])))
                    print("      Resize To: {} ({})".format(resize_to_bytes, convert_bytes_to_storage(resize_to_bytes)))
                    print("-------------------------------------------------------------------------------------------------------------")
                    print(" Volume causing failure:")
                    print_human_readable_volume_dict(pvcs_in_kubernetes[volume_description])
                    print("-------------------------------------------------------------------------------------------------------------")
                    continue

                # Check if we are already at the max volume size (either globally, or this-volume specific)
                if resize_to_bytes == pvcs_in_kubernetes[volume_description]['volume_size_status_bytes']:
                    print("  SKIPPING scaling this because we are at the maximum size of {}".format(convert_bytes_to_storage(pvcs_in_kubernetes[volume_description]['scale_up_max_size'])))
                    continue

                # Check if we set on this PV we want to ignore the volume autoscaler
                if pvcs_in_kubernetes[volume_description]['ignore']:
                    print("  IGNORING scaling this because the ignore annotation was set to true")
                    continue

                # Check if we are DRY-RUN-ing and won't do anything
                if DRY_RUN:
                    print("  DRY RUN was set, but we would have resized this disk from {} to {}".format(convert_bytes_to_storage(pvcs_in_kubernetes[volume_description]['volume_size_status_bytes']), convert_bytes_to_storage(resize_to_bytes)))
                    continue

                # If we aren't dry-run, lets resize
                PROMETHEUS_METRICS['resize_attempted'].inc()
                print("  RESIZING disk from {} to {}".format(convert_bytes_to_storage(pvcs_in_kubernetes[volume_description]['volume_size_status_bytes']), convert_bytes_to_storage(resize_to_bytes)))
                status_output = "to scale up `{}` by `{}%` from `{}` to `{}`, it was using more than `{}%` disk space over the last `{} seconds`".format(
                    volume_description,
                    pvcs_in_kubernetes[volume_description]['scale_up_percent'],
                    convert_bytes_to_storage(pvcs_in_kubernetes[volume_description]['volume_size_status_bytes']),
                    convert_bytes_to_storage(resize_to_bytes),
                    pvcs_in_kubernetes[volume_description]['scale_above_percent'],
                    IN_MEMORY_STORAGE[volume_description] * INTERVAL_TIME
                )
                # Send event that we're starting to request a resize
                send_kubernetes_event(
                    name=volume_name, namespace=volume_namespace, reason="VolumeResizeRequested",
                    message="Requesting {}".format(status_output)
                )

                if scale_up_pvc(volume_namespace, volume_name, resize_to_bytes):
                    PROMETHEUS_METRICS['resize_successful'].inc()
                    status_output = "Successfully requested {}".format(status_output)
                    # Print success to console
                    print(status_output)
                    # Intentionally skipping sending an event to Kubernetes on success, the above event is enough for now until we detect if resize succeeded
                    # Print success to Slack
                    if slack.SLACK_WEBHOOK_URL and len(slack.SLACK_WEBHOOK_URL) > 0:
                        print(f"Sending slack message to {slack.SLACK_CHANNEL}")
                        slack.send(status_output)
                else:
                    PROMETHEUS_METRICS['resize_failure'].inc()
                    status_output = "FAILED requesting {}".format(status_output)
                    # Print failure to console
                    print(status_output)
                    # Print failure to Kubernetes Events
                    send_kubernetes_event(
                        name=volume_name, namespace=volume_namespace, reason="VolumeResizeRequestFailed",
                        message=status_output, type="Warning"
                    )
                    # Print failure to Slack
                    if slack.SLACK_WEBHOOK_URL and len(slack.SLACK_WEBHOOK_URL) > 0:
                        print(f"Sending slack message to {slack.SLACK_CHANNEL}")
                        slack.send(status_output, severity="error")

            except Exception:
                print("Exception caught while trying to process record")
                print(item)
                traceback.print_exc()

        # Wait until our next interval
        time.sleep(MAIN_LOOP_TIME)

    print("We were sent a signal handler to kill, exited gracefully")
    exit(0)
