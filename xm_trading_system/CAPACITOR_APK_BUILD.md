# Zwesta Trader - Capacitor APK Build Guide

This guide explains how to build an Android APK from the Capacitor project.

## 📋 Prerequisites

### System Requirements
- **Android Studio** (latest version) - [Download](https://developer.android.com/studio)
- **Java JDK 17+** - Already installed on your system
- **Node.js** (v16 or higher) - For build tools
- **Gradle** (bundled with Android Studio)

### Verify Installations

```powershell
# Check Node.js
node --version   # Should be v16+

# Check Java
java -version
javac -version

# Check Android Studio
# Open Android Studio and check Tools → SDK Manager
```

## 🏗️ Step 1: Locate Your Capacitor Project

Your Capacitor project should be in:
```
C:\zwesta-trader\
  xm_trading_system\
    (Flask backend files)
  Zwesta-Trader-App\      ← Capacitor project should be here
    android/
    ios/
    src/
    package.json
    capacitor.config.json
```

If you don't have a Capacitor project yet, create one:

```powershell
cd C:\zwesta-trader
npx create-capacitor-app ZwestaTrader --id com.zwesta.trading
cd ZwestaTrader
npm install
```

## 🔧 Step 2: Update Capacitor Configuration

Edit `capacitor.config.json`:

```json
{
  "appId": "com.zwesta.trading",
  "appName": "Zwesta Trader",
  "webDir": "build",
  "server": {
    "url": "https://192.168.0.137:5000",
    "cleartext": true,
    "androidScheme": "https"
  },
  "plugins": {
    "SplashScreen": {
      "launchShowDuration": 3000,
      "launchAutoHide": true,
      "backgroundColor": "#162142",
      "showSpinner": true
    },
    "Network": {},
    "Geolocation": {
      "requestOnInit": false
    }
  }
}
```

**Important**: Update your API server URL if not on local network:
- Local: `https://192.168.0.137:5000`
- Production: Your actual server domain

## 💻 Step 3: Build for Android

### Install Android Build Tools

```powershell
cd path\to\Zwesta-Trader-App

# Install dependencies
npm install

# Add Android platform
npx cap add android

# Sync web files with Android project
npx cap sync android

# Copy Android files
npx cap copy android
```

## 🔨 Step 4: Generate Signed APK

### Option A: Using Android Studio (Recommended for First Build)

```powershell
# Open Android Studio
# File → Open → Select "android" folder from your Capacitor project

# Then:
# Build → Build Bundle(s) / APK(s) → Build APK(s)

# Watch the build progress in Android Studio console
```

### Option B: Using Command Line

```powershell
cd C:\path\to\Zwesta-Trader-App\android

# Build debug APK (for testing)
.\gradlew assembleDebug

# Build release APK (for distribution)
.\gradlew assembleRelease
```

#### Create Keystore for Release Build (Windows)

```powershell
# Navigate to android/app folder
cd android\app

# Create keystore (one-time setup)
keytool -genkey -v -keystore zwesta-release-key.jks `
  -keyalg RSA `
  -keysize 2048 `
  -validity 10000 `
  -alias zwesta-key

# You'll be prompted for:
# Keystore password: [Create a strong password]
# Key password: [Same password or different]
# Name/Organization: Zwesta Trading
# Organizational Unit: Development
# City/Locality: [Your City]
# State/Province: [Your State]
# Country Code: US
# Confirm: Y

# Example output:
# Certificate fingerprint (SHA-256): XX:XX:XX:XX...
```

#### Sign Release APK

```powershell
cd C:\path\to\Zwesta-Trader-App\android\app

# Build and sign
jarsigner -verbose `
  -sigalg SHA1withRSA `
  -digestalg SHA1 `
  -keystore zwesta-release-key.jks `
  build/outputs/apk/release/app-release-unsigned.apk `
  zwesta-key

# Optimize APK
zipalign -v 4 `
  build/outputs/apk/release/app-release-unsigned.apk `
  build/outputs/apk/release/Zwesta-Trader-release.apk

# Final APK is ready at:
# build/outputs/apk/release/Zwesta-Trader-release.apk
```

## 📱 Step 5: Deploy to Android Device

### Option A: Direct Installation

```powershell
adb install C:\path\to\Zwesta-Trader-release.apk
```

### Option B: Via Android Studio

- Device → Logcat → Select your device
- Drag and drop APK onto Android emulator/device

## 🧪 Step 6: Testing

1. **Verify App Starts**
   - Icon appears with name "Zwesta Trader"
   - Splash screen shows (3 seconds)
   - Dashboard loads after

2. **Test Login**
   - Demo username: `demo`
   - Demo password: `demo123`
   - Verify dashboard displays accounts and metrics

3. **Test API Connectivity**
   - Check Settings tab loads user profile
   - Verify Markets tab fetches commodity prices
   - Test that dropdowns work smoothly

4. **Mobile-Specific Testing**
   - Test on different screen sizes
   - Test portrait/landscape rotation
   - Test on slow 4G network (Chrome DevTools throttle)
   - Test touch responsiveness of buttons

## 📦 Distribution

### Google Play Store

1. **Create Developer Account**
   - Go to https://play.google.com/console
   - Pay $25 one-time registration fee
   - Complete merchant account setup

2. **Prepare Listing**
   - App name, description, screenshots
   - Category: Finance
   - Content rating questionnaire
   - Privacy policy
   - Terms of service

3. **Upload APK**
   - Create new app release
   - Upload signed APK (Zwesta-Trader-release.apk)
   - Add release notes
   - Set as production release
   - Submit for review (typically 24-48 hours)

### Direct Distribution

**To share APK directly** (not through store):

```powershell
# Copy signed APK to cloud storage
Copy-Item "Zwesta-Trader-release.apk" C:\path\to\cloud\storage\

# Users can:
# 1. Enable "Unknown Sources" in Android settings
# 2. Download APK from link
# 3. Tap APK to install
```

## 🐛 Debugging

### Enable USB Debugging on Android Device

1. Go to **Settings** → **About Phone**
2. Tap **Build Number** 7 times (to unlock Developer Options)
3. Go to **Settings** → **Developer Options**
4. Enable **USB Debugging**
5. Connect device via USB cable
6. Select **Allow USB Debugging** when prompted

### View Device Logs

```powershell
# Connect device, then:
adb devices

# View logs
adb logcat | grep "Capacitor\|ERROR\|WARN"
```

### Test on Emulator

```powershell
# List available emulators
adb devices

# Run on emulator (slower but useful for testing)
npx cap open android

# In Android Studio: Run → Select Emulator
```

## 📊 APK File Details

### Generated Files

After successful build, you'll have:

```
android/app/build/outputs/apk/
├── release/
│   ├── Zwesta-Trader-release.apk (for distribution)
│   └── app-release-unsigned.apk (intermediate)
└── debug/
    └── app-debug.apk (for testing)
```

### File Information

- **Zwesta-Trader-release.apk**
  - Size: ~50-80 MB
  - Signed with your keystore
  - Ready for Google Play or direct distribution
  - Contains all JS/HTML bundled
  - Includes Android SDK libraries

- **app-debug.apk**
  - Smaller, unoptimized
  - Only for development testing
  - Don't distribute to users

## ⚡ Performance Optimization

### Reduce APK Size

In `android/app/build.gradle`:

```gradle
android {
    bundle {
        language {
            // Reduce languages
            enableSplit = false
        }
    }
}
```

### Enable Proguard Minification

In `android/app/build.gradle`:

```gradle
buildTypes {
    release {
        minifyEnabled true
        shrinkResources true
        proguardFiles getDefaultProguardFile('proguard-android.txt'), 'proguard-rules.pro'
    }
}
```

## 🔐 Security Checklist

- [ ] API server uses HTTPS (not HTTP)
- [ ] Sensitive data not hardcoded in app
- [ ] Used signed APK (not debug)
- [ ] Keystore password stored securely
- [ ] No API keys in source code
- [ ] Data encrypted in transit (HTTPS)
- [ ] User authentication required for sensitive operations

## 🚀 Deployment Checklist

- [ ] App tested on multiple Android versions (6.0 - 14+)
- [ ] App tested on different screen sizes (phone, tablet)
- [ ] All features working (login, dashboard, markets, settings)
- [ ] WhatsApp alerts configured (if enabled)
- [ ] API server URL correct for your environment
- [ ] Server SSL certificate trusted by Android
- [ ] Performance acceptable (<3s initial load)
- [ ] No crashes or force closes
- [ ] App properly exits/minimizes on back press

## 📞 Support

### Common Issues

**"Build failed: ANDROID_SDK_ROOT not found"**
```powershell
setx ANDROID_SDK_ROOT "C:\Users\%USERNAME%\AppData\Local\Android\Sdk"
# Restart PowerShell
```

**"Permission denied" on Linux**
```bash
chmod +x gradlew
```

**App loads blank screen**
- Check server URL in capacitor.config.json
- Verify HTTPS certificate is valid
- Check browser console: Chrome DevTools via `chrome://inspect`

**API calls fail on device**
- Verify device has internet connection
- Check if your server URL is accessible from device
- Test with: `ping 192.168.0.137` (if on same network)
- For production: Use your actual domain name, not IP

### Additional Resources

- **Ionic Docs**: https://ionicframework.com/docs
- **Capacitor Docs**: https://capacitorjs.com/docs
- **Android Dev**: https://developer.android.com/
- **Build Troubleshooting**: https://capacitorjs.com/docs/android

## 📝 Notes

- Store your keystore file safely - you'll need it for future updates
- APK version number in `android/app/build.gradle` must increase for updates
- Each release should have unique version code
- Test builds thoroughly before distribution

---

**Next Steps After Build:**

1. ✅ Test on Android device
2. ✅ Verify all features work
3. ✅ Optimize performance if needed
4. ✅ Set up crash reporting (Firebase Crashlytics optional)
5. ✅ Deploy to Google Play or distribute directly
6. ✅ Monitor user feedback and logs
