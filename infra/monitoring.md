# Monitoring and alerting

The API emits structured JSON request logs with method, path, status code and latency. `/metrics` exposes status-class counters that can be scraped by Prometheus-compatible collectors.

Suggested production alerts:

- 5XX rate above 1% for 5 minutes.
- 4XX rate above baseline by 3 standard deviations for 10 minutes.
- p95 latency above 500 ms for 5 minutes.
- `/ready` failing for 2 consecutive checks.
- Exchange refresh failures for 2 consecutive refresh windows.

Dashboard panels:

- request rate by route and status class
- p50/p95/p99 latency
- transfer failures and insufficient-funds conflicts
- database connection saturation
- exchange rate age by currency
