// retrieve data embedded in referrer <script>
const scriptElem = document.currentScript;
const VOTE_POST_ENDPOINT_TEMPLATE = scriptElem.dataset.votePostEndpointTemplate;
const LOGIN_URL = scriptElem.dataset.loginUrl;
const USER_PROFILE_ENDPOINT_TEMPLATE = scriptElem.dataset.userProfileEndpointTemplate;
const CSRF_TOKEN = scriptElem.dataset.csrfToken;
const UUID4_PLACEHOLDER = "00000000-0000-0000-0000-000000000000";

// frontpage
const SHOW_POST_ENDPOINT_TEMPLATE = scriptElem.dataset.showPostEndpointTemplate;
const GET_POSTS_ENDPOINT = scriptElem.dataset.getPostsEndpoint;
// show_post (already has the page's postid)
const GET_POST_ENDPOINT = scriptElem.dataset.getPostEndpoint;
const GET_COMMENTS_ENDPOINT = scriptElem.dataset.getCommentsEndpoint;
const CREATE_COMMENT_ENDPOINT = scriptElem.dataset.createCommentEndpoint;
const VOTE_COMMENT_ENDPOINT_TEMPLATE = scriptElem.dataset.voteCommentEndpointTemplate;

let postsAbortController;
function generatePostElem(post, show_links=true) {
    let postElem = document.createElement("article");
    postElem.id = post.id;
    postElem.classList.add("post", "shadow", "hover--expand");
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
                <a class="button button--small post__actions__share" href="https://www.youtube.com/watch?v=dQw4w9WgXcQ">
                    <i class="fa-solid fa-link"></i>
                    Share
                </a>
            </div>
        </div>`;
    
    const postLink = show_links 
        ? `<a href="${show_post_url}" class="post__show-anchor">&#8203;</a>`
        : ``;

    const postInnerHtml = `
        ${postLink}
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

    return postElem;
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

        const userProfilePage = USER_PROFILE_ENDPOINT_TEMPLATE.replace(UUID4_PLACEHOLDER, comment.user_id);
        commentElem.innerHTML = `
            <img class="comment__pfp" src="/static/img/judge.jpg" alt="">
            ${commentRepliesToHtml}
            <div class="comment__body">
                <a href="${userProfilePage}" class="comment__body__username">${comment.username}</a>
                <div class="comment__body__content">${comment.content}</div>
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
    });

    return commentTree;
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
    } finally {
        vote_button_set.dataset.requestPending = "false";
        vote_button_set.removeAttribute("aria-busy");
    }
}
