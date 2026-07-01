# Guntamatic (read/write) — Home Assistant integration

A HACS-installable custom integration for [Guntamatic](https://www.guntamatic.com/)
biomass/pellet heaters. It reads **all** DAQ channels the device exposes and adds
**control** (writes) on top — using **API-key** authentication.

It talks to the same local HTTP/CGI web interface as the
[`guntamatic`](https://github.com/swimmesberger/guntamatic) Rust project
(`/ext/daqdesc.cgi`, `/ext/daqdata.cgi`, `/ext/parset.cgi`).

## Why this exists (vs. the official integration)

Home Assistant ships an **official** `guntamatic` integration (since 2026.6). It is
excellent for monitoring but **read-only**, HTTP-only, keyless, and exposes a curated
subset of sensors. This integration is a superset focused on the gaps:

| | Official `guntamatic` | This integration |
|---|---|---|
| Sensors | curated (~11) | **every** DAQ channel (dynamic) |
| Boolean channels | as sensors | as **binary sensors** |
| Control / writes | ❌ none | ✅ boiler release, control program, per-circuit heating program, hot-water reload |
| Auth | keyless (root endpoints) | **API key** (`/ext/` endpoints) |
| Discovery | DHCP | DHCP |
| Transport | HTTP polling | HTTP polling |

> If you only need monitoring, the official integration + the built-in InfluxDB
> integration is the simplest path. Use this one when you want control and/or
> the full channel set.

## Install (HACS)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/swimmesberger/ha-guntamatic`, category **Integration**.
2. Install **Guntamatic (read/write)** and restart Home Assistant.
3. Settings → Devices & Services → **Add Integration** → *Guntamatic (read/write)*.
   A `kessel…` device may also be auto-discovered via DHCP.

Manual install: copy `custom_components/guntamatic_rw/` into your HA `config/custom_components/` folder and restart.

## Configuration

- **Host** — IP or hostname of the heater.
- **API key** — the device key with authorization level **W1** or higher (required
  for both data access *and* commands). Get it from your Guntamatic BCE /
  registration. Without a sufficient level the endpoints return no data and setup fails.

Options (Settings → the integration → **Configure**):

- **Polling interval** (default 30 s)
- **Number of heating circuits** (0–9) — creates one program select per circuit `HK0…HK8`
- **Number of hot-water circuits** (0–3) — creates reload buttons per circuit
- **Boiler product family** — picks the correct boiler-release command:
  `PK002` (Powerchip/Powercorn/Biocom/Pro) or `K0010` (Therm/Biostar)

## Entities

- **Sensors** — one per numeric/text DAQ channel, with inferred units/device classes.
- **Binary sensors** — one per boolean DAQ channel.
- **Selects** (writes):
  - *Boiler release* — Auto / Off / On
  - *Control program* — Off / Normal / Hot water / Heating / Setback / Manual
  - *Heating circuit N program* — Off / Normal / Heating / Setback
- **Buttons** (writes) — *Hot water N reload*, *Additional hot water N reload*

### A note on control state

- **Control program** and **per-circuit heating program** selects reflect the
  **real device state**, read from the `Programm` / `Progamm HKx` DAQ string
  channels.
- The **boiler release** select is **optimistic** (shows the last command issued
  from Home Assistant, restored across restarts), because the device only exposes
  a boolean `Kesselfreigabe` channel that can't distinguish Auto from On.

Writes are always sent live and validated against the device's `ack`/`err` reply.

## ⚠️ Safety

Per the Guntamatic interface terms, remote control **must not alter the operating
behaviour** of the appliance in a harmful way (e.g. rapidly toggling the boiler on/off
like an oil burner causes serious malfunctions on biomass heaters). Only use the
customer-level (W1) authorization, and make sure the installation is safe for remote
operation. Use at your own risk.

## Command reference (protocol)

All writes are `GET /ext/parset.cgi?syn=<SYN>&value=<V>&key=<KEY>`:

| Control | syn | values |
|---|---|---|
| Boiler release | `PK002` / `K0010` | 0=Auto, 1=Off, 2=On |
| Control program | `PR001` | 0=Off, 1=Normal, 2=HotWater, 3=Heat, 4=Setback, 8=Manual |
| Heating circuit x (0–8) | `HK{x}01` | 0=Off, 1=Normal, 2=Heat, 3=Setback |
| Hot-water reload x (0–2) | `BK{x}06` | 1=reload |
| Add. hot-water reload x (0–2) | `ZK{x}06` | 1=reload |

## Logging to InfluxDB

Add Home Assistant's built-in [InfluxDB integration](https://www.home-assistant.io/integrations/influxdb/)
and include `sensor.guntamatic_rw_*` / `binary_sensor.guntamatic_rw_*`.

## License

MIT
