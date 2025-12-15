# Attack Scripts

**⚠️ WARNING: Educational and authorized security testing only**

## Purpose

These scripts are **NMEA protocol parser robustness testing tools** for Application-layer DoS demonstration in authorized maritime OT security research.

### What These Are:
- ✅ Parser Robustness Test (견고성 검증)
- ✅ Application-layer DoS demonstration
- ✅ Protocol compliance testing
- ✅ IDS detection verification

### What These Are NOT:
- ❌ GPS Spoofing (not coordinate manipulation)
- ❌ Logic Attack (not control logic tampering)
- ❌ Network Flooding (not bandwidth exhaustion)
- ❌ Real attack tools

---

## Scripts

### 1. `nmea_fuzzer.py` - NMEA Protocol Parser Fuzzer

**Type:** Application-layer DoS via Malformed NMEA Sentences

**Target:** NMEA parsers (OpenCPN, navigation software)

**Techniques:**
1. **Line Length Overflow** - 65KB payload (parser crash/hang)
2. **Malformed Checksum** - Invalid checksum format
3. **Control Character Injection** - Null bytes, escape chars
4. **Field Explosion** - 2000+ fields (memory exhaustion)

**Usage:**
```bash
# UDP-only mode (manual verification required)
python3 nmea_fuzzer.py --host 10.10.10.10 --attack random --duration 60

# With HTTP health check (recommended)
python3 nmea_fuzzer.py --host 10.10.10.10 \
  --attack overflow \
  --duration 120 \
  --health-url http://10.10.10.10:8080/
```

**Success Detection:**

⚠️ **UDP Limitation:** Cannot automatically detect crashes (no response mechanism)

✅ **Proper Verification:**
1. **Bridge Zone (A) Observation:**
   - [ ] OpenCPN UI freeze/crash
   - [ ] Process CPU/Memory spike (`htop`, `top`)
   - [ ] Logs show parsing errors
   - [ ] Process still running? (`ps aux | grep OpenCPN`)

2. **Integration Zone (B) Detection:**
   - [ ] Suricata IDS alerts for malformed NMEA
   - [ ] Network anomaly detection triggers

3. **HTTP Health Endpoint (Optional, Recommended):**
   - Deploy HTTP server on Bridge: `python3 -m http.server 8080`
   - Fuzzer queries endpoint to detect crashes
   - More reliable than UDP-only

**Known Limitations:**
- **IP Fragmentation:** 65KB UDP may fragment, effectiveness varies by environment
- **Parser Implementation:** Some parsers handle errors gracefully (no crash, just ignore)
- **Target Behavior:** May freeze instead of crash - both are valid results
- **MTU limits:** Large packets may be silently dropped

**Demonstration Checklist:**
```
✅ Before Attack:
[ ] Screenshot: Bridge Zone - OpenCPN running normally
[ ] Screenshot: Bridge Zone - CPU/Memory baseline (htop)
[ ] Screenshot: Integration Zone - Suricata ready

🚨 During Attack:
[ ] Screenshot: Fuzzer running with statistics
[ ] Screenshot: Bridge Zone - OpenCPN frozen/crashed
[ ] Screenshot: Bridge Zone - CPU spike or high memory
[ ] Screenshot: Integration Zone - Suricata alerts

✅ After Attack:
[ ] Screenshot: Fuzzer final statistics
[ ] Screenshot: Bridge Zone - Process status (ps aux)
[ ] Screenshot: Integration Zone - Suricata logs
```

---

## Attack Scenarios

### Scenario: NMEA Parser Robustness Testing

**Zones:**
- **A (Bridge):** Victim - Runs OpenCPN/NMEA listener
- **B (Integration):** Defender - Runs Suricata IDS
- **C (Control):** Witness - Monitors both zones
- **Attacker VM:** Executes fuzzer

**Flow:**
1. **Setup:**
   - Bridge (A): OpenCPN receiving NMEA on UDP 10110
   - Integration (B): Suricata monitoring traffic
   - Attacker: Ready to fuzz

2. **Attack:**
   - Attacker executes `nmea_fuzzer.py` with mixed attacks
   - Bridge (A): Parser struggles with malformed packets
   - Integration (B): IDS detects protocol violations

3. **Results:**
   - Bridge (A): OpenCPN freezes/crashes, CPU spikes
   - Integration (B): Suricata alerts trigger
   - Control (C): Verifies impact and detection

**Success Criteria:**
- Parser demonstrates lack of robustness (freeze/crash/error)
- IDS successfully detects malformed protocol
- System impact is measurable (CPU, memory, logs)

---

## Environment Setup

### Bridge Zone (A) - Target
```bash
# Run NMEA listener or OpenCPN
# Listen on UDP port 10110

# Optional: HTTP health server
python3 -m http.server 8080
```

### Integration Zone (B) - IDS
```bash
# Run Suricata with NMEA detection rules
sudo suricata -c /etc/suricata/suricata.yaml -i eth0

# Monitor alerts
tail -f /var/log/suricata/fast.log
```

### Attacker VM
```bash
cd attacker

# Test run (10 seconds, slow)
python3 nmea_fuzzer.py --host 10.10.10.10 --attack random --duration 10 --interval 0.2

# Real test (60 seconds, normal speed)
python3 nmea_fuzzer.py --host 10.10.10.10 --attack overflow --duration 60 --interval 0.05

# With HTTP health check
python3 nmea_fuzzer.py --host 10.10.10.10 \
  --attack random \
  --duration 120 \
  --health-url http://10.10.10.10:8080/
```

---

## Responsible Disclosure

These tools are for:
- ✅ Educational purposes in controlled lab environments
- ✅ Authorized security testing with written permission
- ✅ IDS/IPS rule development and testing
- ✅ Parser robustness evaluation

Do NOT use for:
- ❌ Unauthorized testing on production systems
- ❌ Attacking real ships or navigation systems
- ❌ Any illegal or malicious activity

**Always obtain proper authorization before testing.**

---

## References

**NMEA Protocol:**
- NMEA 0183 Standard
- Maximum sentence length: 82 characters
- Checksum format: `$SENTENCE*XX\r\n`

**Parser Testing:**
- Fuzzing for robustness
- Boundary value analysis
- Error handling verification

**Related CVEs:**
- GPS parser vulnerabilities
- NMEA parsing issues in navigation software
- Protocol implementation flaws

---

## License

Educational use only. See project LICENSE for details.
