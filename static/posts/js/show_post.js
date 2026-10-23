// dependency: posts/js/posts.js
window.addEventListener('load', function() {
    getPost();
    getComments();
    const createCommentForm = document.getElementById("comment-form");
    if (createCommentForm) {
        createCommentForm.addEventListener('submit', function(e) {
            e.preventDefault();
            createComment();
        });
    }
});
