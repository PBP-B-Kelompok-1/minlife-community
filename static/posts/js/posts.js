// retrieve data embedded in referrer <script>
const scriptElem = document.currentScript;
const VOTE_POST_ENDPOINT_TEMPLATE = scriptElem.dataset.votePostEndpointTemplate;
const UPDATE_POST_ENDPOINT_TEMPLATE = scriptElem.dataset.updatePostEndpointTemplate;
const DELETE_POST_ENDPOINT_TEMPLATE = scriptElem.dataset.deletePostEndpointTemplate;
const DELETE_COMMENT_ENDPOINT_TEMPLATE = scriptElem.dataset.deleteCommentEndpointTemplate;
const LOGIN_URL = scriptElem.dataset.loginUrl;
const USER_PROFILE_ENDPOINT_TEMPLATE = scriptElem.dataset.userProfileEndpointTemplate;
const CSRF_TOKEN = scriptElem.dataset.csrfToken;
const UUID4_PLACEHOLDER = "00000000-0000-0000-0000-000000000000";
const QUOTES_ENDPOINT = "https://jovan-finesta-minimalist-quotes-api.pws.cs.ui.ac.id/random"
const FALLBACK_PFP = "/static/img/pfp.svg";

// frontpage
const SHOW_POST_ENDPOINT_TEMPLATE = scriptElem.dataset.showPostEndpointTemplate;
const GET_POSTS_ENDPOINT = scriptElem.dataset.getPostsEndpoint;
// show_post (already has the page's postid)
const GET_POST_ENDPOINT = scriptElem.dataset.getPostEndpoint;
const GET_COMMENTS_ENDPOINT = scriptElem.dataset.getCommentsEndpoint;
const CREATE_COMMENT_ENDPOINT = scriptElem.dataset.createCommentEndpoint;
const VOTE_COMMENT_ENDPOINT_TEMPLATE = scriptElem.dataset.voteCommentEndpointTemplate;

const KEBAB_CONTAINER_SELECTOR = ".post__kebab-container, .comment__kebab-container";

function closeKebabMenus(except = null) {
    document.querySelectorAll(KEBAB_CONTAINER_SELECTOR).forEach((container) => {
        if (container === except) return;

        container.querySelector(".post__kebab, .comment__kebab").classList.remove("shown");
        container.querySelector(".post__kebab-btn, .comment__kebab-btn")
            .setAttribute("aria-expanded", "false");
    });
}

function toggleKebabMenu(container) {
    closeKebabMenus(container);

    const kebab = container.querySelector(".post__kebab, .comment__kebab");
    const button = container.querySelector(".post__kebab-btn, .comment__kebab-btn");
    const isShown = kebab.classList.toggle("shown");
    button.setAttribute("aria-expanded", isShown);
}

document.addEventListener("click", (event) => {
    closeKebabMenus(event.target.closest(KEBAB_CONTAINER_SELECTOR));
});

document.addEventListener("focusin", (event) => {
    closeKebabMenus(event.target.closest(KEBAB_CONTAINER_SELECTOR));
});

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeKebabMenus();
});

let postsAbortController;
function generatePostElem(post, show_links=true) {
    let postElem = document.createElement("article");
    postElem.id = post.id;
    postElem.classList.add("post", "shadow", "hover--expand");

    const userProfilePage = USER_PROFILE_ENDPOINT_TEMPLATE.replace(UUID4_PLACEHOLDER, post.user_id);
    let authorInfoHtml = `
        <a href="${userProfilePage}" class="post__author">
            <img class="post__author__pfp" 
                src="${post.avatar_url}" 
                onerror="this.onerror=null; this.src='${FALLBACK_PFP}';"
                alt="${post.username}'s profile picture">
            <span class="post__author__username">${post.username}</span>
        </a>`;

    const updateDisabled = post.can_update ? "" : " button--disabled";
    const deleteDisabled = post.can_delete ? "" : " button--disabled";
    let firstRowHtml = `
        <div class="post__first-row">
            ${authorInfoHtml}
            <div class="post__kebab-container">
                <button
                    class="post__kebab-btn"
                    type="button"
                    aria-haspopup="menu"
                    aria-expanded="false"
                    aria-controls="post-${post.id}__kebab"
                    aria-label="More post actions">
                    <i class="fa-solid fa-ellipsis"></i>
                </button>
                <div id="post-${post.id}__kebab" class="post__kebab shadow" role="menu">
                    <button class="button button--border button--small post__update-btn${updateDisabled}" type="button" role="menuitem"${post.can_update ? "" : " disabled"}>
                        <i class="fa-solid fa-pen-to-square"></i>
                        Update
                    </button>
                    <button class="button button--danger button--small post__delete-btn${deleteDisabled}" type="button" role="menuitem"${post.can_delete ? "" : " disabled"}>
                        <i class="fa-solid fa-trash-can"></i>
                        Delete
                    </button>
                </div>
            </div>
        </div>
    `;

    let postTitleHtml = `
        <div class="post__title">
            <h1>${post.title}</h1>
        </div>`; // TODO: sanitize
    
    let postTagsHtml = `<div class="post__tags">`;
    post.tags.forEach(tag => {
        postTagsHtml += `
            <button class="post__tag button button--small">
                ${tag.title}
            </button>`;
    });
    postTagsHtml += `</div>`;
    
    let postContentHtml = `
        <div class="post__content">
            ${post.content}
        </div>`;
    
    let updootClass = post.user_vote_value == 1 ? ` upvoted` : ``;
    let downdootClass = post.user_vote_value == -1 ? ` downvoted` : ``;
    
    const show_post_url = SHOW_POST_ENDPOINT_TEMPLATE.replace(UUID4_PLACEHOLDER, post.id)
    const comment_href = show_links
        ? `href="${show_post_url}"`
        : ``;
    let postActionsHtml = `
        <div class="post__actions">
            <div class="post__actions--left">
                <div class="post__actions__vote button--no-hover button button--small button--border">
                    <button class="post__actions__upvote fa-solid fa-chevron-up${updootClass}"></button>
                    <span class="post__actions__vote-count">${post.vote_count}</span>
                    <button class="post__actions__downvote fa-solid fa-chevron-down${downdootClass}"></button>
                </div>
                <a class="post__actions__comment button button--small button--border"${comment_href}>
                    <i class="fa-solid fa-comment"></i>
                    <span class="post__actions__comment-count">${post.comment_count}</span>
                </a>
            </div>
            <div class="post__actions--right">
                <button class="button button--small post__actions__share"
                    data-show-post-url=${show_post_url}>
                    <i class="fa-solid fa-link"></i>
                    Share
                </button>
            </div>
        </div>`;
    
    const postLink = show_links 
        ? `<a href="${show_post_url}" class="post__show-anchor">&#8203;</a>`
        : ``;

    const postInnerHtml = `
        ${postLink}
        ${firstRowHtml}
        ${postTitleHtml}
        ${postTagsHtml}
        ${postContentHtml}
        ${postActionsHtml}
    `;

    postElem.innerHTML = postInnerHtml;

    postElem.querySelector(".post__actions__upvote").addEventListener("click", (e) => {
        e.preventDefault();
        vote_post(e.target, 1);
    });
    postElem.querySelector(".post__actions__downvote").addEventListener("click", (e) => {
        e.preventDefault();
        vote_post(e.target, -1);
    });
    postElem.querySelector(".post__actions__share").addEventListener("click", (e) => {
        e.preventDefault();
        copy_post_url_to_clipboard(e.target);
    });
    postElem.querySelector(".post__kebab-btn").addEventListener("click", (event) => {
        event.preventDefault();
        toggleKebabMenu(event.currentTarget.closest(".post__kebab-container"));
    });
    postElem.querySelector(".post__update-btn").addEventListener("click", (event) => {
        window.location.assign(UPDATE_POST_ENDPOINT_TEMPLATE.replace(UUID4_PLACEHOLDER, post.id));
    });
    postElem.querySelector(".post__delete-btn").addEventListener("click", (event) => {
        deletePost(event.currentTarget);
    });

    return postElem;
}

async function deletePost(deleteButton) {
    const postElem = deleteButton.closest("article.post");
    if (!postElem || deleteButton.disabled || deleteButton.dataset.requestPending === "true" || deleteButton.dataset.confirming === "true") return;

    deleteButton.dataset.confirming = "true";
    const confirmation = await Swal.fire({
        title: "Delete this post?",
        text: "This will permanently delete the post and all of its comments.",
        icon: "warning",
        showCancelButton: true,
        confirmButtonText: "Delete post",
        cancelButtonText: "Cancel",
        confirmButtonColor: "var(--danger)",
    });
    deleteButton.dataset.confirming = "false";
    if (!confirmation.isConfirmed) return;

    deleteButton.dataset.requestPending = "true";
    deleteButton.disabled = true;
    try {
        const response = await fetch(
            DELETE_POST_ENDPOINT_TEMPLATE.replace(UUID4_PLACEHOLDER, postElem.id),
            {
                method: "POST",
                headers: { "Accept": "application/json", "X-CSRFToken": CSRF_TOKEN || getCookie("csrftoken") },
            }
        );
        const data = await response.json().catch(() => ({}));
        if (response.status === 401) {
            const loginUrl = data.login_url || LOGIN_URL;
            window.location.assign(`${loginUrl}?next=${encodeURIComponent(window.location.href)}`);
            return;
        }
        if (!response.ok) throw new Error(`Delete request failed with status ${response.status}`);

        toast.fire({ icon: "success", title: "Post deleted successfully." });
        // A post detail page cannot display a deleted post; the feed can simply
        // remove its card without navigating away.
        if (GET_POST_ENDPOINT) {
            window.location.assign("/");
        } else {
            postElem.remove();
            const postsContainer = document.getElementById("posts");
            if (!postsContainer.children.length) {
                document.getElementById("posts__status").innerText = "No posts were found... Come again later!";
            }
        }
    } catch (error) {
        console.error("Error deleting post:", error);
        toast.fire({ icon: "error", title: "Something went wrong while deleting the post..." });
        deleteButton.disabled = false;
    } finally {
        deleteButton.dataset.requestPending = "false";
    }
}

async function getPost() {
    if (postsAbortController) postsAbortController.abort();
    postsAbortController = new AbortController();

    const postsContainer = document.getElementById("posts");
    const postsStatusElem = document.getElementById("posts__status");
    try {
        postsContainer.innerHTML = "";
        postsStatusElem.innerText = "Loading...";
        const response = await fetch(GET_POST_ENDPOINT, {
            method: "GET",
            headers: { "Accept": "application/json" },
            signal: postsAbortController.signal,
        });
        
        if (response.status === 404) {
            postsStatusElem.innerText = "Sorry, that post doesn't exist!";
            throw new Error(`Get request failed with status ${response.status}`);
        } else if (!response.ok) {
            postsStatusElem.innerText = "An error occured while fetching data...";
            throw new Error(`Get request failed with status ${response.status}`);
        }
        const data = (await response.json()).data;

        if (data.length === 0) {
            postsStatusElem.innerText = "Received an empty response... contact server admininstrators!";
            throw new Error(`Received an empty response`);
        } else {
            postsStatusElem.innerText = "";
            let postElem = generatePostElem(data, show_links=false);
            postsContainer.append(postElem);
        }
    } catch (error) {
        if (error.name == 'AbortError') return;
        console.error(`An error occured: ${error}`);
    }
}

async function getPosts() {
    if (postsAbortController) postsAbortController.abort();
    postsAbortController = new AbortController();

    const postsContainer = document.getElementById("posts");
    const postsStatusElem = document.getElementById("posts__status");
    try {
        postsContainer.innerHTML = "";
        postsStatusElem.innerText = "Loading...";
        const response = await fetch(GET_POSTS_ENDPOINT, {
            method: "GET",
            headers: { "Accept": "application/json" },
            signal: postsAbortController.signal,
        });
        
        if (!response.ok) {
            throw new Error(`Get request failed with status ${response.status}`);
        }

        const data = (await response.json()).data;
        if (data.length === 0) {
            postsStatusElem.innerText = "No posts were found... Come again later!";
        } else {
            postsStatusElem.innerText = "";
            data.forEach(post => {
                let postElem = generatePostElem(post);
                postsContainer.append(postElem);
            });
        }
    } catch (error) {
        if (error.name == 'AbortError') return;
        console.error(`An error occured: ${error}`);
        postsStatusElem.innerText = "An error occured while fetching data...";
    }
}

// un-upvote still counts as 1
async function vote_post(vote_button, vote_value) {
    const post_id = vote_button.closest("article").id;
    const vote_button_set = vote_button.closest(".post__actions__vote");
    const vote_count_elem = vote_button_set.querySelector(".post__actions__vote-count");
    if (vote_button_set.dataset.requestPending == "true") return;
    if (vote_value != 1 && vote_value != -1) {
        console.error("Error: You can't just vote 'neutral'!");
        return;
    }

    // Loading state (immediate response, just in case the server goes slow for some reason)
    // a bit ugly but i think it's necessary
    const prev_vote_value = vote_count_elem.textContent;
    vote_count_elem.textContent = "...";

    vote_button_set.dataset.requestPending = "true";
    vote_button_set.setAttribute("aria-busy", "true");

    const endpoint = VOTE_POST_ENDPOINT_TEMPLATE.replace(UUID4_PLACEHOLDER, post_id);
    try {
        const response = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Accept": "application/json",
                "X-CSRFToken": CSRF_TOKEN || getCookie("csrftoken")
            },
            body: JSON.stringify({"vote_value": vote_value})
        });
        const data = await response.json();
        
        if (response.status === 401) {
            const login_url = data.login_url || LOGIN_URL
            // works the same way as login_required
            window.location.assign(`${login_url}?next=${encodeURIComponent(window.location.href)}`);
            return;
        }
        
        if (!response.ok) {
            throw new Error(`Vote request failed with status ${response.status}`);
        }
        
        // renew status
        vote_button_set.querySelector(".post__actions__upvote")
            .classList.toggle("upvoted", data.vote_value === 1);
        vote_button_set.querySelector(".post__actions__downvote")
            .classList.toggle("downvoted", data.vote_value === -1);
        vote_count_elem.textContent = data.vote_count;
    } catch(error){
        vote_count_elem.textContent = prev_vote_value;
        console.error(`An error occured while voting: ${error}`)
    } finally {
        vote_button_set.dataset.requestPending = "false";
        vote_button_set.removeAttribute("aria-busy");
    }
}

// === Comments ===
let commentsAbortController;
async function getComments() {
    if (commentsAbortController) commentsAbortController.abort();
    commentsAbortController = new AbortController();

    const commentsContainer = document.getElementById("comments");
    const commentsStatusElem = document.getElementById("comments__status");
    try {
        commentsContainer.innerHTML = "";
        commentsStatusElem.innerText = ""; 
        const response = await fetch(GET_COMMENTS_ENDPOINT, {
            method: "GET",
            headers: { "Accept": "application/json" },
            signal: commentsAbortController.signal,
        });
        
        if (!response.ok) {
            commentsStatusElem.innerText = "An error occured while fetching data...";
            throw new Error(`Get request failed with status ${response.status}`);
        }
        const data = (await response.json()).data;

        if (data.length === 0) {
            commentsStatusElem.innerText = "Be the first to comment on this post!";
        } else {
            commentsStatusElem.innerText = "";
            let commentElem = generateCommentTree(data);
            commentsContainer.append(commentElem);
        }
    } catch (error) {
        if (error.name == 'AbortError') return;
        console.error(`An error occured: ${error}`);
    }
}

function generateCommentTree(comments, repliesToElemId=null, repliesToUser=null) {
    const commentTree = document.createDocumentFragment();

    comments.forEach(comment => {
        let commentElem = document.createElement("article");
        commentElem.id = comment.id;
        commentElem.classList.add("comment", "shadow", "hover--expand");

        let commentRepliesToHtml = repliesToElemId
            ? `<a href="#${repliesToElemId}" class="comment__replies-to">
                    <i class="fa-solid fa-reply"></i> ${repliesToUser}
                </a>`
            : ``;
    
        let updootClass = comment.user_vote_value == 1 ? ` upvoted` : ``;
        let downdootClass = comment.user_vote_value == -1 ? ` downvoted` : ``;

        const userProfilePage = comment.is_deleted
            ? null
            : USER_PROFILE_ENDPOINT_TEMPLATE.replace(UUID4_PLACEHOLDER, comment.user_id);
        const commentAuthorHtml = comment.is_deleted
            ? `<span class="comment__body__username">${comment.username}</span>`
            : `<a href="${userProfilePage}" class="comment__body__username">${comment.username}</a>`;
        const deleteDisabled = comment.can_delete ? "" : " button--disabled";
        commentElem.innerHTML = `
            <img class="comment__pfp" 
                src="${comment.is_deleted ? FALLBACK_PFP : comment.avatar_url}"
                onerror="this.onerror=null; this.src='${FALLBACK_PFP}';"
                alt="${comment.username}'s profile picture">
            ${commentRepliesToHtml}
            <div class="comment__body">
                ${commentAuthorHtml}
                <div class="comment__body__content">${comment.content}</div>
            </div>
            <div class="comment__kebab-container">
                <button
                    class="comment__kebab-btn"
                    type="button"
                    aria-haspopup="menu"
                    aria-expanded="false"
                    aria-controls="comment-${comment.id}__kebab"
                    aria-label="More comment actions">
                    <i class="fa-solid fa-ellipsis"></i>
                </button>
                <div id="comment-${comment.id}__kebab" class="comment__kebab shadow" role="menu">
                    <button class="button button--danger button--small comment__delete-btn${deleteDisabled}" type="button" role="menuitem"${comment.can_delete ? "" : " disabled"}>
                        <i class="fa-solid fa-trash-can"></i>
                        Delete
                    </button>
                </div>
            </div>
            <div class="comment__actions">
                <div class="comment__actions__vote button button--small button--border button--no-hover">
                    <button class="comment__actions__upvote fa-solid fa-chevron-up${updootClass}"></button>
                    <span class="comment__actions__vote-count">${comment.vote_count}</span>
                    <button class="comment__actions__downvote fa-solid fa-chevron-down${downdootClass}"></button>
                </div>
                <button class="comment__actions__reply button button--border button--small">
                    <i class="fa-solid fa-reply"></i>${comment.reply_count}
                </button>
            </div>`;

        commentTree.append(commentElem);

        if (comment.replies.length > 0) {
            const repliesElem = document.createElement("div");
            repliesElem.classList.add("comment__replies");
            repliesElem.append(generateCommentTree(comment.replies, comment.id, comment.username));

            commentTree.append(repliesElem);
        }

        commentElem.querySelector(".comment__actions__upvote").addEventListener("click", (e) => {
            e.preventDefault();
            vote_comment(e.target, 1);
        });
        commentElem.querySelector(".comment__actions__downvote").addEventListener("click", (e) => {
            e.preventDefault();
            vote_comment(e.target, -1);
        });
        commentElem.querySelector(".comment__actions__reply").addEventListener("click", (e) => {
            e.preventDefault();
            toggleReplyForm(commentElem, comment.id);
        });
        commentElem.querySelector(".comment__kebab-btn").addEventListener("click", (event) => {
            toggleKebabMenu(event.currentTarget.closest(".comment__kebab-container"));
        });
        commentElem.querySelector(".comment__delete-btn").addEventListener("click", (event) => {
            deleteComment(event.currentTarget);
        });
    });

    return commentTree;
}

async function deleteComment(deleteButton) {
    const commentElem = deleteButton.closest("article.comment");
    if (!commentElem || deleteButton.disabled || deleteButton.dataset.requestPending === "true" || deleteButton.dataset.confirming === "true") return;

    deleteButton.dataset.confirming = "true";
    const confirmation = await Swal.fire({
        title: "Delete this comment?",
        text: "This cannot be undone. Replies to this comment will also be deleted.",
        icon: "warning",
        showCancelButton: true,
        confirmButtonText: "Delete comment",
        cancelButtonText: "Cancel",
        confirmButtonColor: "var(--danger)",
    });
    deleteButton.dataset.confirming = "false";
    if (!confirmation.isConfirmed) return;

    deleteButton.dataset.requestPending = "true";
    deleteButton.disabled = true;
    try {
        const response = await fetch(
            DELETE_COMMENT_ENDPOINT_TEMPLATE.replace(UUID4_PLACEHOLDER, commentElem.id),
            {
                method: "POST",
                headers: { "Accept": "application/json", "X-CSRFToken": CSRF_TOKEN || getCookie("csrftoken") },
            }
        );
        const data = await response.json().catch(() => ({}));
        if (response.status === 401) {
            const loginUrl = data.login_url || LOGIN_URL;
            window.location.assign(`${loginUrl}?next=${encodeURIComponent(window.location.href)}`);
            return;
        }
        if (!response.ok) throw new Error(`Delete request failed with status ${response.status}`);

        toast.fire({ icon: "success", title: "Comment deleted successfully." });
        await getComments();
    } catch (error) {
        console.error("Error deleting comment:", error);
        toast.fire({ icon: "error", title: "Something went wrong while deleting the comment..." });
        deleteButton.disabled = false;
    } finally {
        deleteButton.dataset.requestPending = "false";
    }
}

function toggleReplyForm(commentElem, commentId) {
    const oldReplyForm = commentElem.querySelector(".comment__reply-form");
    if (oldReplyForm) {
        oldReplyForm.remove();
        return;
    }

    const replyFormTemplate = document.getElementById("reply-form-template");
    const replyForm = replyFormTemplate.content.firstElementChild.cloneNode(true);
    const contentField = replyForm.querySelector("textarea[name='content']");
    const oldFieldId = contentField.id;
    const replyFieldId = `${oldFieldId}-${commentId}`;

    // The widget has a few elements based on its textarea ID. Rename all of
    // them before adding the copy to the page, otherwise CKEditor sees them as
    // the same editor as another reply form.
    replyForm.querySelectorAll("[id], [for], [data-field-id]").forEach((elem) => {
        ["id", "for", "data-field-id"].forEach((attribute) => {
            if (elem.hasAttribute(attribute)) {
                elem.setAttribute(attribute, elem.getAttribute(attribute).replaceAll(oldFieldId, replyFieldId));
            }
        });
    });
    replyForm.querySelector("input[name='replies_to_comment']").value = commentId;

    // django-ckeditor-5 watches for the copied widget and creates the editor
    // once it is inserted into the page. Register before inserting so we can
    // grab its data when submitting the reply.
    replyForm.editorPromise = new Promise((resolve) => {
        window.ckeditorRegisterCallback(replyFieldId, resolve);
    });

    replyForm.addEventListener("submit", (e) => {
        e.preventDefault();
        createComment(replyForm);
    });
    replyForm.querySelector("button[type='button']").addEventListener("click", () => replyForm.remove());

    const repliesElem = commentElem.querySelector(":scope > .comment__replies");
    if (repliesElem) {
        commentElem.insertBefore(replyForm, repliesElem);
    } else {
        commentElem.append(replyForm);
    }
}

async function createComment(createCommentForm = document.getElementById("comment-form")) {
    let ckeditorField = createCommentForm.id === "comment-form"
        ? window.editors['id_content']
        : null;
    if (createCommentForm.editorPromise) {
        ckeditorField = await createCommentForm.editorPromise;
        createCommentForm.querySelector("textarea[name='content']").value = ckeditorField.getData();
    }
    const createCommentSubmitButton = createCommentForm.querySelector("button[type='submit']");
    createCommentSubmitButton.disabled = true;
    try {
        const response = await fetch(CREATE_COMMENT_ENDPOINT, {
            method: 'POST',
            headers: { "X-CSRFToken": CSRF_TOKEN || getCookie("csrftoken") },
            body: new FormData(createCommentForm)
        });
        const result = await response.json().catch(() => ({}));

        if (response.status === 401) {
            const login_url = result.login_url || LOGIN_URL
            window.location.assign(`${login_url}?next=${encodeURIComponent(window.location.href)}`);
            return;
        }

        if (!response.ok) {
            const errorMessages = result.errors
                ? Object.values(result.errors).flat().map(error => error.message)
                : [result.message || `Something went wrong (status ${response.status}).`];
            throw new Error(`${errorMessages}`);
        } else {
            toast.fire({
                icon: "success",
                title: "Successfully posted the comment!"
            });
            createCommentForm.reset();
            if (ckeditorField) ckeditorField.setData(''); // special handling needed
            if (createCommentForm.classList.contains("comment__reply-form")) createCommentForm.remove();
            await getComments();
            window.location.hash = result.comment_id;
        }
    } catch(error) {
        toast.fire({
            icon: "error",
            title: "Something went wrong while uploading the comment..."
        });
        console.error('Error adding comment:', error);
    } finally {
        createCommentSubmitButton.disabled = false;
    }
}

async function vote_comment(vote_button, vote_value) {
    const comment_id = vote_button.closest("article").id;
    const vote_button_set = vote_button.closest(".comment__actions__vote");
    const vote_count_elem = vote_button_set.querySelector(".comment__actions__vote-count");
    if (vote_button_set.dataset.requestPending == "true") return;
    if (vote_value != 1 && vote_value != -1) {
        console.error("Error: You can't just vote 'neutral'!");
        return;
    }

    // Loading state (immediate response, just in case the server goes slow for some reason)
    // a bit ugly but i think it's necessary
    const prev_vote_value = vote_count_elem.textContent;
    vote_count_elem.textContent = "...";

    vote_button_set.dataset.requestPending = "true";
    vote_button_set.setAttribute("aria-busy", "true");

    const endpoint = VOTE_COMMENT_ENDPOINT_TEMPLATE.replace(UUID4_PLACEHOLDER, comment_id);
    try {
        const response = await fetch(endpoint, {
            method: "POST",
            headers: {
                "Accept": "application/json",
                "X-CSRFToken": CSRF_TOKEN || getCookie("csrftoken")
            },
            body: JSON.stringify({"vote_value": vote_value})
        });
        const data = await response.json();
        
        if (response.status === 401) {
            const login_url = data.login_url || LOGIN_URL
            // works the same way as login_required
            window.location.assign(`${login_url}?next=${encodeURIComponent(window.location.href)}`);
            return;
        }
        
        if (!response.ok) {
            if (data.error) { // expected error that should be user friendly.
                vote_count_elem.textContent = prev_vote_value;
                toast.fire({
                    icon: "error",
                    title: `An error occured: ${data.error}`
                });
                console.error(`An error occured while voting: ${data.error}`)
                return;
            }
            throw new Error(`Vote request failed with status ${response.status}`);
        }
        
        // renew status
        vote_button_set.querySelector(".comment__actions__upvote")
            .classList.toggle("upvoted", data.vote_value === 1);
        vote_button_set.querySelector(".comment__actions__downvote")
            .classList.toggle("downvoted", data.vote_value === -1);
        vote_count_elem.textContent = data.vote_count;
    } catch(error){
        vote_count_elem.textContent = prev_vote_value;
        console.error(`An error occured while voting: ${error}`)
        toast.fire({
            icon: "error",
            title: "Something went wrong while voting..."
        });
    } finally {
        vote_button_set.dataset.requestPending = "false";
        vote_button_set.removeAttribute("aria-busy");
    }
}

function copy_post_url_to_clipboard(share_btn) {
    try {
        const location_str = String(document.location);
        const location_str_trimmed = location_str.endsWith('/') ? location_str.slice(0, -1) : str;
        const show_post_url = location_str_trimmed + share_btn.dataset.showPostUrl;
        navigator.clipboard.writeText(show_post_url);
        toast.fire({
            icon: "success",
            title: "Copied to clipboard!"
        });
    } catch (error) {
        toast.fire({
            icon: "error",
            title: "Failed to copy to clipboard..."
        });
        console.error(`An error occured while copying: ${error}`)
    }
}

async function showQuote() {
    quoteTextElem = document.getElementById("quote__text");
    quoteByElem = document.getElementById("quote__by");

    try {
        const response = await fetch(QUOTES_ENDPOINT, {
            method: "GET",
            headers: { "Accept": "application/json" },
        });
        
        if (!response.ok) {
            throw new Error(`Get request failed with status ${response.status}`);
        }
        const data = (await response.json()).data;
        if (data.length === 0) {
            throw new Error(`Quote API returned empty.`);
        }
        quoteTextElem.innerText = `"${data["quote"]}"`;
        quoteByElem.innerText = `— ${data["author"]}, ${data["year"]}`;
    } catch (error) {
        console.error(`An error occured: ${error}`);
    }
}
