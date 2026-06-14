"""Generate Splunk alert stanzas and search definitions."""


def build_error_rate_search(service_name: str) -> str:
    return (
        f'index=main sourcetype=autoops service="{service_name}" '
        '| stats count(eval(level="ERROR")) as errors, count as total '
        "| eval error_rate=if(total>0, errors/total*100, 0) "
        "| where error_rate > 5"
    )


def build_latency_search(service_name: str, threshold_ms: int = 500) -> str:
    return (
        f'index=main sourcetype=autoops service="{service_name}" '
        f"| stats avg(duration_ms) as avg_latency "
        f"| where avg_latency > {threshold_ms}"
    )


def build_alert_stanza(
    alert_name: str,
    search: str,
    description: str,
) -> dict[str, str]:
    return {
        "name": alert_name,
        "search": search,
        "description": description,
        "alert_type": "number of events",
        "alert_comparator": "greater than",
        "alert_threshold": "0",
    }


def build_p95_latency_search(threshold_ms: int = 1000) -> str:
    return (
        "index=main sourcetype=autoops "
        f"| stats p95(duration_ms) as p95 "
        f"| where p95 > {threshold_ms}"
    )


def build_db_latency_search(threshold_ms: int = 300) -> str:
    return (
        "index=main sourcetype=autoops event_type=db_query "
        f"| stats avg(query_duration_ms) as avg_db_ms "
        f"| where avg_db_ms > {threshold_ms}"
    )


def build_no_data_search() -> str:
    return (
        "index=main sourcetype=autoops earliest=-15m "
        "| stats count as events "
        "| where events < 1"
    )


def build_5xx_spike_search() -> str:
    return (
        'index=main sourcetype=autoops status>=500 '
        "| timechart span=1m count as errors "
        "| where errors > 5"
    )


def build_deployment_search() -> str:
    return (
        "index=main (sourcetype=autoops:event OR event_type=deployment) "
        "| sort - _time | head 20"
    )


def build_checkout_alert(app_name: str) -> dict[str, str]:
    search = (
        'index=main sourcetype=autoops path="/checkout" '
        "| stats count(eval(level=\"ERROR\")) as errors, count as total "
        "| eval error_rate=if(total>0, errors/total*100, 0) "
        "| where error_rate > 10"
    )
    return build_alert_stanza(
        f"autoops_{app_name}_checkout_error_rate",
        search,
        "Checkout error rate exceeded 10%",
    )
