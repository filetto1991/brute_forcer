
# 🔐 Async Login Brute-Forcer

A minimal yet **high-speed** login brute-force tool written in Python 3 using `asyncio` and `aiohttp`.

> ⚠️ **Ethics & Legal**  
> Only use this tool against **targets you own or have explicit written permission to test**.  
> Unauthorized brute-forcing is illegal in most jurisdictions.

---

## ✨ Features

- **Asynchronous** – hundreds of login attempts per second  
- **JSON or form payloads** – flexible `^USER^` / `^PASS^` templating  
- **Thread-safe concurrency** – adjustable via `-t`  
- **Progress bar** – live feedback with `tqdm`  
- **SSL toggle** – ignore or verify certificates  
- **Clean exit on Ctrl-C**

---

## 🚀 Quick Start

### 1. Install

```bash
pip install aiohttp tqdm colorama
````

### 2. Run

```bash
python brute_forcer.py https://testsite.local/login \
    -u admin@testsite.local \
    -w rockyou-mini.txt \
    --form '{"email":"^USER^","password":"^PASS^"}' \
    -t 50 --timeout 3
```

---

## 🧰 CLI Options

|Flag|Default|Description|
|:--|:--|:--|
|`url` (positional)|—|Login endpoint|
|`-u, --username`|—|Username / email|
|`-w, --wordlist`|—|Text file with passwords|
|`--form`|`{"email":"^USER^","password":"^PASS^"}`|Payload template (`^USER^` & `^PASS^`)|
|`-m, --method`|`POST`|HTTP method (`POST` or `GET`)|
|`-t, --threads`|`20`|Concurrent requests|
|`--timeout`|`5`|Socket timeout (s)|
|`--verify-ssl`|_disabled_|Enforce certificate validation|

---

## 🎯 Payload Examples

### JSON login body

```bash
--form '{"username":"^USER^","password":"^PASS^"}'
```

### URL-encoded form

```bash
--form 'username=^USER^&password=^PASS^'
```

### GET query parameters

```bash
-m GET --form 'user=^USER^&pass=^PASS^'
```

---

## 🛑 Stopping the Scan

Press `Ctrl-C` at any time – running tasks are cancelled gracefully.

---

## 🛠️ Troubleshooting

| Problem       | Fix                                                   |
| :------------ | :---------------------------------------------------- |
| SSL errors    | add `--verify-ssl` if cert is valid, otherwise ignore |
| 403 responses | change User-Agent in source, or add custom headers    |
| Rate-limiting | lower `-t` or increase `--timeout`                    |

---

# 🛡️ Legal Disclaimer
This tool is intended for educational purposes and for testing on domains you own or have explicit permission to test. Unauthorized use against third-party domains may be illegal.
