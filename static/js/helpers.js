window.addEventListener('load', function () {
    watchForHover();
});

function getCookie(name) {
    const cookie = document.cookie.split("; ").find((item) => item.startsWith(`${name}=`));
    return cookie ? decodeURIComponent(cookie.split("=")[1]) : "";
}

/* CSS disable hover */
// Source - https://stackoverflow.com/a/30303898
// Posted by blade, modified by community. See post 'Timeline' for change history
// Retrieved 2026-10-21, License - CC BY-SA 4.0
function watchForHover() {
  // lastTouchTime is used for ignoring emulated mousemove events
  let lastTouchTime = 0

  function enableHover() {
    if (new Date() - lastTouchTime < 500) return
    document.body.classList.add('has-hover')
  }

  function disableHover() {
    document.body.classList.remove('has-hover')
  }

  function updateLastTouchTime() {
    lastTouchTime = new Date()
  }

  document.addEventListener('touchstart', updateLastTouchTime, true)
  document.addEventListener('touchstart', disableHover, true)
  document.addEventListener('mousemove', enableHover, true)

  enableHover()
}

/* Toast format that is used in every app */
/* CARA PAKAI: lihat di bawah */
const toast = Swal.mixin({
  toast: true,
  position: "top-end",
  showConfirmButton: false,
  timer: 3000,
  timerProgressBar: true,
  didOpen: (toast) => {
    toast.onmouseenter = Swal.stopTimer;
    toast.onmouseleave = Swal.resumeTimer;
  }
})

/* CONTOH PEMAKAIAN
toast.fire({
  icon: "success|error|warning|info",
  title: "Pesan"
});
*/
