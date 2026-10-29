importScripts(
    "https://www.gstatic.com/firebasejs/{{ firebase_web_sdk_version }}/firebase-app-compat.js"
);
importScripts(
    "https://www.gstatic.com/firebasejs/{{ firebase_web_sdk_version }}/firebase-messaging-compat.js"
);

const firebaseConfig = JSON.parse(
    "{{ firebase_web_config_json|escapejs }}"
);

firebase.initializeApp(firebaseConfig);
firebase.messaging();
