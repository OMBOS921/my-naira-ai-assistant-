import asyncio
from backend.modules.remote_bridge.fcm_manager import FCMDispatcher

def test_firebase():
    print("Checking Firebase Credentials...")
    dispatcher = FCMDispatcher()
    
    # Initialize function call karke check kar rahe hain
    is_connected = dispatcher.initialize_firebase()
    
    if is_connected:
        print("✅ BOOM! Firebase Credentials successfully connected and working!")
    else:
        print("❌ Oops! File nahi mili ya JSON mein koi gadbad hai.")

if __name__ == "__main__":
    test_firebase()