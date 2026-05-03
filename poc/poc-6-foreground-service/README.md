# PoC-6: Android Foreground Service Spike

> Verifies that a long-running foreground service survives 12+ hours on the
> 6 major Chinese ROMs (red-mi/Honor/OPPO/vivo/Meizu/AOSP). This is the spine of
> 🟡 passive-hint mode (engineering plan §3 PoC-6 + product design §11.1).
>
> **You must run this on a real Android device.** No Android SDK exists on the
> dev box where this code was authored.

## Why this PoC matters

If the foreground service dies after 4-6 hours on any major ROM, passive-hint
mode is fundamentally broken — and that breaks the product's soul.

Hard verdict criteria (mirrors §3 PoC-6 validation standard):

| ROM | Target survival | Pass threshold |
|---|---|---|
| Xiaomi MIUI / HyperOS | 12h | ≥ 90% across 3 phones |
| Honor MagicOS         | 12h | ≥ 90% across 3 phones |
| OPPO ColorOS          | 12h | ≥ 90% across 3 phones |
| vivo OriginOS         | 12h | ≥ 90% across 3 phones |
| Meizu Flyme           | 12h | optional, lower priority |
| AOSP / Pixel          | 12h | ≥ 95% (control group)   |

Pass = service stays alive **and the heartbeat counter increments without gaps
larger than 60 s** for 12h+, on at least 3 phones across the 4 priority ROMs.

## What this app does

The minimal foreground service:
  1. Posts a sticky notification ("LiveT 正在监听 PoC-6 测试")
  2. Increments a heartbeat counter every 5 seconds
  3. Writes each heartbeat tick to `/sdcard/Android/data/io.livet.poc6/files/heartbeat.csv`
     with timestamp + counter
  4. Exposes the live counter on the main screen

After 12+ hours, you collect the CSV and check for gaps. Any gap > 60 s
indicates the OS killed and resumed (or just killed) the service.

## How to run

### Option A: Android Studio (easiest)

1. Install Android Studio (Iguana 2023.2.1 or newer)
2. `File → Open` and select this directory (`poc/poc-6-foreground-service`)
3. Let Gradle sync. Accept any SDK install prompts (target SDK 34, min SDK 26)
4. Connect your test phone via USB, enable USB debugging
5. Click `Run` (green triangle)
6. After install, the app shows a counter; the service keeps running in the
   background even after you close the app

**Important**: Battery optimization MUST be disabled for the app:
  - Settings → Apps → LiveT-PoC6 → Battery → Don't optimize
  - On MIUI: also enable "Autostart" in Permissions

The app shows guidance on first launch; tap "打开电池白名单设置" to jump there.

### Option B: Command-line Gradle (if you don't want Android Studio)

```bash
# Prerequisites: Android SDK + JDK 17 installed, ANDROID_HOME set
# Generate the Gradle wrapper first time:
gradle wrapper --gradle-version 8.5

# Build & install
./gradlew assembleDebug
./gradlew installDebug

# Launch on connected device
adb shell am start -n io.livet.poc6/.MainActivity
```

### Option C: integrate into the main RN app

Once the bare Android project here proves the foreground service survives,
the `LiveTForegroundService.kt` + `BatteryWhitelistHelper.kt` files can be
copied verbatim into `app/android/app/src/main/java/io/livet/app/native/`
and exposed to RN via a TurboModule.

## How to verify pass / fail

After 12+ hours of leaving the device idle (screen off, plugged in is fine
for first run; unplugged for second run):

```bash
# Pull the heartbeat CSV
adb pull /sdcard/Android/data/io.livet.poc6/files/heartbeat.csv

# Run the gap analyzer (pure Python, no deps)
python3 analyze_heartbeat.py heartbeat.csv
```

The analyzer reports:
  - total runtime
  - count of gaps > 60 s
  - longest gap
  - verdict (PASS / FAIL)

Then update `results.md` with the per-ROM result and commit it.

## File map

```
poc/poc-6-foreground-service/
├── README.md                          ← you are here
├── settings.gradle.kts
├── build.gradle.kts
├── gradle.properties
├── analyze_heartbeat.py               ← post-test gap analyzer (Python)
├── results.md                         ← write per-ROM results here
└── app/
    ├── build.gradle.kts
    ├── proguard-rules.pro
    └── src/main/
        ├── AndroidManifest.xml
        ├── java/io/livet/poc6/
        │   ├── MainActivity.kt
        │   ├── LiveTForegroundService.kt
        │   ├── HeartbeatLogger.kt
        │   └── BatteryWhitelistHelper.kt
        └── res/
            ├── layout/activity_main.xml
            ├── values/strings.xml
            └── values/themes.xml
```

## Known caveats

- This PoC does NOT include audio capture; that comes in PoC-1/PoC-2 and is
  what triggers the "MICROPHONE" foreground service type. Here we use type
  `dataSync` to keep the test simple while still being a real foreground
  service.
- The privacy commitment "永不保留原声" doesn't apply to this PoC (no audio).
- This PoC writes to external storage for ease of pulling via adb. The
  production app uses internal storage only.
