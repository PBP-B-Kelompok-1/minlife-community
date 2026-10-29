const announcementDialog = document.getElementById("announcement-dialog");
const announcementDialogContent = document.getElementById(
    "announcement-dialog-content",
);

announcementDialogContent.addEventListener("htmx:afterSwap", () => {
    if (!announcementDialog.open) {
        announcementDialog.showModal();
    }
});

announcementDialog.addEventListener("click", (event) => {
    if (event.target.closest("[data-close-announcement-dialog]")) {
        announcementDialog.close();
    }
});

document.addEventListener("announcement-changed", (event) => {
    announcementDialog.close();
    toast.fire({
        icon: "success",
        title: event.detail.message,
    });
});
