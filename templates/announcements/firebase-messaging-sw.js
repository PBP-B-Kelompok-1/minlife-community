self.addEventListener("install", () => {
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(clients.claim());
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    const firebaseMessage = event.notification.data?.FCM_MSG;
    const link = event.notification.data?.link
        || firebaseMessage?.fcmOptions?.link
        || firebaseMessage?.data?.announcement_url
        || "/announcements/";

    event.waitUntil(
        clients.matchAll({ type: "window", includeUncontrolled: true })
            .then((windowClients) => {
                const existingClient = windowClients[0];
                if (existingClient) {
                    return existingClient.navigate(link)
                        .then(() => existingClient.focus());
                }
                return clients.openWindow(link);
            })
    );
});

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
