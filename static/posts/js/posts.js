window.addEventListener('load', function() {
    getPosts();
});

// retrieve data embedded in referrer <script>
const scriptElem = document.currentScript;
const GET_POSTS_ENDPOINT = scriptElem.dataset.getPostsEndpoint;
const SHOW_POST_ENDPOINT_TEMPLATE = scriptElem.dataset.showPostEndpointTemplate;
const VOTE_POST_ENDPOINT_TEMPLATE = scriptElem.dataset.votePostEndpointTemplate;
const LOGIN_URL = scriptElem.dataset.loginUrl;
const CSRF_TOKEN = scriptElem.dataset.csrfToken;
const POST_ID_PLACEHOLDER = "00000000-0000-0000-0000-000000000000";

let postsAbortController;
function generatePostElem(post) {
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
    
    const show_post_url = SHOW_POST_ENDPOINT_TEMPLATE.replace(POST_ID_PLACEHOLDER, post.id)
    let postActionsHtml = `
        <div class="post__actions">
            <div class="post__actions--left">
                <div class="post__actions__vote button--no-hover button button--small button--border">
                    <button class="post__actions__upvote fa-solid fa-chevron-up${updootClass}"></button>
                    <span class="post__actions__vote-count">${post.vote_count}</span>
                    <button class="post__actions__downvote fa-solid fa-chevron-down${downdootClass}"></button>
                </div>
                <a class="post__actions__comment button button--small button--border" href="${show_post_url}">
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
    
    const postInnerHtml = `
        <a href="${show_post_url}" class="post__show-anchor">&#8203;</a>
        ${postTitleHtml}
        ${postTagsHtml}
        ${postContentHtml}
        ${postActionsHtml}
    `;

    postElem.innerHTML = postInnerHtml;

    postElem.querySelector(".post__actions__upvote").addEventListener("click", (e) => {
        e.preventDefault();
        vote(e.target, 1);
    });
    postElem.querySelector(".post__actions__downvote").addEventListener("click", (e) => {
        e.preventDefault();
        vote(e.target, -1);
    });

    return postElem;
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
        const data = (await response.json()).data;
        
        if (!response.ok) {
            throw new Error(`Get request failed with status ${response.status}`);
        }

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
async function vote(vote_button, vote_value) {
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

    const endpoint = VOTE_POST_ENDPOINT_TEMPLATE.replace(POST_ID_PLACEHOLDER, post_id);
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
