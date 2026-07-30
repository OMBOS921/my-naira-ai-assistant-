# Firebase FCM Integration Setup Guide

Follow these steps to complete the Firebase Cloud Messaging (FCM) setup for the Naira-OS Remote Android App:

## 1. Create Firebase Project
1. Open the [Firebase Console](https://console.firebase.google.com).
2. Click **Add project** (or **Create a project**).
3. Name the project **NairaOS** and complete the project creation wizard.

## 2. Register Android Application
1. In the Firebase project overview page, click the **Android icon** (`+ Add app` -> Android).
2. Enter the Android Package Name:
   ```
   com.naira.remote
   ```
3. Optionally enter an app nickname (e.g., `Naira-OS Remote App`).
4. Click **Register app**.

## 3. Add `google-services.json` Configuration File
1. Download the `google-services.json` file provided by Firebase.
2. Move/copy the downloaded `google-services.json` into the `naira_android_app/app/` folder:
   ```
   naira_android_app/app/google-services.json
   ```

## 4. Enable Firebase Cloud Messaging API
1. In the Firebase Console, open **Project Settings** (gear icon next to Project Overview).
2. Select the **Cloud Messaging** tab.
3. If Cloud Messaging API (Legacy) or Firebase Cloud Messaging API v1 is disabled, click the triple dots menu / link to open **Google Cloud Console** and click **Enable**.

## 5. Configure PC Backend Server Key
1. In the Firebase Console → **Project Settings** → **Cloud Messaging** tab, locate your **Server Key** (or standard credentials).
2. Copy the key value.
3. Paste the key into your PC backend's `config.py` as:
   ```python
   FCM_SERVER_KEY = "YOUR_FIREBASE_SERVER_KEY_HERE"
   ```
