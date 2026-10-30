import { initializeApp } from "https://www.gstatic.com/firebasejs/13.1.0/firebase-app.js";
import {
    getMessaging,
    isSupported,
    onMessage,
    onRegistered,
    onUnregistered,
    register,
    unregister,
} from "https://www.gstatic.com/firebasejs/13.1.0/firebase-messaging.js";

const toggle = document.getElementById("notification-toggle");
const configElement = document.getElementById("firebase-web-config");
const settingsElement = document.getElementById("firebase-notification-settings");
const preferenceKey = "minlife-notifications-enabled";

let messaging;
let currentInstallationId = null;
let requestInProgress = false;
let registrationWasRequestedByUser = false;
let statusToastQueue = Promise.resolve();

function wait(milliseconds) {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function showStatus(message, icon = "info", position = "top-end") {
    if (window.Swal) {
        statusToastQueue = statusToastQueue
            .then(async () => {
                while (window.Swal.isVisible()) {
                    await wait(150);
                }
                await window.Swal.fire({
                    toast: true,
                    position,
                    showConfirmButton: false,
                    timer: 3000,
                    timerProgressBar: true,
                    icon,
                    title: message,
                });
            })
            .catch((error) => {
                console.error("Could not display notification status.", error);
            });
        return;
    }

    const region = document.getElementById("toast-region");
    if (region) region.textContent = message;
}

async function showSystemNotification(payload) {
    const registration = await navigator.serviceWorker.ready;
    const title = payload.notification?.title || "New announcement";
    const body = payload.notification?.body || "A new update is available.";
    const link = payload.fcmOptions?.link
        || payload.data?.announcement_url
        || "/announcements/";

    await registration.showNotification(title, {
        body,
        data: { link },
    });
}

function setButtonState(state) {
    if (!toggle) return;

    const label = toggle.querySelector("span");
    const icon = toggle.querySelector("i");

    toggle.disabled = state === "loading" || state === "unsupported";
    toggle.setAttribute("aria-pressed", state === "enabled" ? "true" : "false");
    toggle.dataset.state = state;

    if (state === "enabled") {
        label.textContent = "Disable Notifications";
        icon.className = "fa-solid fa-bell";
    } else if (state === "loading") {
        label.textContent = "Updating Notifications...";
        icon.className = "fa-solid fa-spinner fa-spin";
    } else if (state === "unsupported") {
        label.textContent = "Notifications Unavailable";
        icon.className = "fa-regular fa-bell-slash";
    } else {
        label.textContent = "Enable Notifications";
        icon.className = "fa-regular fa-bell";
    }
}

async function syncSubscription(url, installationId) {
    const response = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": window.getCookie("csrftoken"),
        },
        body: JSON.stringify({ installation_id: installationId }),
    });

    if (!response.ok) {
        throw new Error(`Subscription request failed with status ${response.status}.`);
    }
}

async function enableNotifications(showConfirmation = false) {
    setButtonState("loading");
    registrationWasRequestedByUser = showConfirmation;

    const permission = Notification.permission === "granted"
        ? "granted"
        : await Notification.requestPermission();

    if (permission !== "granted") {
        registrationWasRequestedByUser = false;
        localStorage.setItem(preferenceKey, "false");
        setButtonState(permission === "denied" ? "unsupported" : "disabled");
        showStatus("Notification permission was not granted.", "warning");
        return;
    }

    localStorage.setItem(preferenceKey, "true");
    try {
        await register(messaging, {
            vapidKey: settingsElement.dataset.vapidKey,
            serviceWorkerRegistration: await navigator.serviceWorker.ready,
        });
    } catch (error) {
        registrationWasRequestedByUser = false;
        throw error;
    }
}

async function disableNotifications() {
    setButtonState("loading");
    localStorage.setItem(preferenceKey, "false");

    if (currentInstallationId) {
        await syncSubscription(
            settingsElement.dataset.unsubscribeUrl,
            currentInstallationId,
        );
    }

    await unregister(messaging);
    currentInstallationId = null;
    setButtonState("disabled");
    showStatus("Notifications disabled.", "success");
}

async function initializeNotifications() {
    if (!configElement || !settingsElement) return;
    setButtonState("loading");

    const supported = "Notification" in window
        && "serviceWorker" in navigator
        && await isSupported();
    if (!supported) {
        setButtonState("unsupported");
        return;
    }

    const app = initializeApp(JSON.parse(configElement.textContent));
    messaging = getMessaging(app);

    await navigator.serviceWorker.register(
        settingsElement.dataset.serviceWorkerUrl,
        { scope: "/" },
    );

    onRegistered(messaging, async (installationId) => {
        currentInstallationId = installationId;
        try {
            await syncSubscription(
                settingsElement.dataset.subscribeUrl,
                installationId,
            );
            setButtonState("enabled");
            if (registrationWasRequestedByUser) {
                showStatus("Notifications enabled.", "success");
            }
            registrationWasRequestedByUser = false;
        } catch (error) {
            registrationWasRequestedByUser = false;
            console.error(error);
            setButtonState("disabled");
            showStatus("Could not enable notifications.", "error");
        }
    });

    onUnregistered(messaging, async (installationId) => {
        try {
            await syncSubscription(
                settingsElement.dataset.unsubscribeUrl,
                installationId,
            );
        } catch (error) {
            console.error(error);
        }
    });

    onMessage(messaging, (payload) => {
        showSystemNotification(payload).catch((error) => {
            console.error("Could not display system notification.", error);
        });
    });

    if (
        Notification.permission === "granted"
        && localStorage.getItem(preferenceKey) !== "false"
    ) {
        await enableNotifications();
    } else if (Notification.permission === "denied") {
        setButtonState("unsupported");
    } else {
        setButtonState("disabled");
    }
}

if (toggle) {
    toggle.addEventListener("click", async () => {
        if (requestInProgress) return;
        requestInProgress = true;

        try {
            if (toggle.dataset.state === "enabled") {
                await disableNotifications();
            } else {
                await enableNotifications(true);
            }
        } catch (error) {
            console.error(error);
            setButtonState("disabled");
            showStatus("Could not update notifications.", "error");
        } finally {
            requestInProgress = false;
        }
    });
}

initializeNotifications().catch((error) => {
    console.error(error);
    setButtonState("unsupported");
    if (toggle) {
        showStatus("Notifications are unavailable.", "error");
    }
});
