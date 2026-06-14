"""Generate Splunk Simple XML dashboards."""

DASHBOARD_TEMPLATE = """
<dashboard version="1.1">
  <label>{app_name} — Service Health</label>
  <row>
    <panel>
      <title>Error Rate — {service_name}</title>
      <chart>
        <search>
          <query>
index=main sourcetype=autoops service={service_name}
| timechart span=1m count(eval(level="ERROR")) as errors, count as total
| eval error_rate=if(total>0, errors/total*100, 0)
          </query>
          <earliest>-1h</earliest>
          <latest>now</latest>
        </search>
        <option name="charting.chart">area</option>
      </chart>
    </panel>
  </row>
  <row>
    <panel>
      <title>Latency — {service_name}</title>
      <chart>
        <search>
          <query>
index=main sourcetype=autoops service={service_name}
| timechart span=1m avg(duration_ms) as avg_latency_ms p95(duration_ms) as p95_latency_ms
          </query>
          <earliest>-1h</earliest>
          <latest>now</latest>
        </search>
        <option name="charting.chart">line</option>
      </chart>
    </panel>
  </row>
</dashboard>
"""


OVERVIEW_TEMPLATE = """
<dashboard version="1.1">
  <label>{app_name} — Service Health Overview</label>
  <row>
    <panel>
      <title>Global Error Rate</title>
      <chart>
        <search>
          <query>
index=main sourcetype=autoops
| timechart span=1m count(eval(level="ERROR")) as errors, count as total
| eval error_rate=if(total>0, errors/total*100, 0)
          </query>
          <earliest>-24h</earliest>
          <latest>now</latest>
        </search>
        <option name="charting.chart">area</option>
      </chart>
    </panel>
  </row>
  <row>
    <panel>
      <title>Checkout Latency</title>
      <chart>
        <search>
          <query>
index=main sourcetype=autoops path="/checkout"
| timechart span=1m avg(duration_ms) as avg_ms p95(duration_ms) as p95_ms
          </query>
          <earliest>-24h</earliest>
          <latest>now</latest>
        </search>
        <option name="charting.chart">line</option>
      </chart>
    </panel>
  </row>
</dashboard>
"""


DB_DASHBOARD_TEMPLATE = """
<dashboard version="1.1">
  <label>{app_name} — Database Performance</label>
  <row>
    <panel>
      <title>Query Duration by Database</title>
      <chart>
        <search>
          <query>
index=main sourcetype=autoops event_type=db_query
| timechart span=1m avg(query_duration_ms) by database
          </query>
          <earliest>-1h</earliest>
          <latest>now</latest>
        </search>
        <option name="charting.chart">line</option>
      </chart>
    </panel>
  </row>
</dashboard>
"""


def build_service_dashboard(app_name: str, service_name: str) -> str:
    return DASHBOARD_TEMPLATE.format(app_name=app_name, service_name=service_name).strip()


def build_overview_dashboard(app_name: str) -> str:
    return OVERVIEW_TEMPLATE.format(app_name=app_name).strip()


def build_database_dashboard(app_name: str) -> str:
    return DB_DASHBOARD_TEMPLATE.format(app_name=app_name).strip()


DEPLOYMENT_TEMPLATE = """
<dashboard version="1.1">
  <label>{app_name} — Deployment Timeline</label>
  <row>
    <panel>
      <title>Deployments and Config Changes</title>
      <table>
        <search>
          <query>
index=main (sourcetype=autoops:event OR event_type=deployment)
| sort - _time
| table _time, service, version, event_type, message
          </query>
          <earliest>-24h</earliest>
          <latest>now</latest>
        </search>
      </table>
    </panel>
  </row>
</dashboard>
"""


INCIDENT_TEMPLATE = """
<dashboard version="1.1">
  <label>{app_name} — Incident Investigation</label>
  <row>
    <panel>
      <title>Error Logs (last hour)</title>
      <table>
        <search>
          <query>
index=main sourcetype=autoops level=ERROR
| sort - _time
| table _time, service, path, message, trace_id
          </query>
          <earliest>-1h</earliest>
          <latest>now</latest>
        </search>
      </table>
    </panel>
  </row>
  <row>
    <panel>
      <title>Latency vs Errors</title>
      <chart>
        <search>
          <query>
index=main sourcetype=autoops
| timechart span=1m avg(duration_ms) as avg_ms, count(eval(level="ERROR")) as errors
          </query>
          <earliest>-1h</earliest>
          <latest>now</latest>
        </search>
        <option name="charting.chart">line</option>
      </chart>
    </panel>
  </row>
</dashboard>
"""


def build_deployment_dashboard(app_name: str) -> str:
    return DEPLOYMENT_TEMPLATE.format(app_name=app_name).strip()


def build_incident_dashboard(app_name: str) -> str:
    return INCIDENT_TEMPLATE.format(app_name=app_name).strip()
