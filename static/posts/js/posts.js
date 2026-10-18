// retrieve data embedded in referrer <script>
const scriptElem = document.currentScript;
const GET_POSTS_ENDPOINT = scriptElem.dataset.getPostsEndpoint;

const postsContainer = document.getElementById("posts");
const postsStatusElem = document.getElementById("posts__status");
let postsAbortController;
function generatePostElem(post) {
    let postElem = document.createElement("article");
    postElem.id = post.id;
    postElem.classList.add("post", "shadow");
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
    
    let postActionsHtml = `
        <div class="post__actions">
            <div class="post__actions--left">
                <div class="post__actions__vote button--no-hover button button--small button--border">
                    <a class="post__actions__upvote fa-solid fa-chevron-up${updootClass}"></a>
                    <span class="post__actions__vote-count">${post.vote_count}</span>
                    <a class="post__actions__downvote fa-solid fa-chevron-down${downdootClass}"></a>
                </div>
                <a class="post__actions__comment button button--small button--border" href="#">
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
        ${postTitleHtml}
        ${postTagsHtml}
        ${postContentHtml}
        ${postActionsHtml}
    `;

    postElem.innerHTML = postInnerHtml;
    return postElem;
}

async function getPosts() {
    if (postsAbortController) postsAbortController.abort();
    postsAbortController = new AbortController();
    try {
        postsContainer.innerHTML = "";
        postsStatusElem.innerText = "Loading...";
        const response = await fetch(GET_POSTS_ENDPOINT, {
            method: "GET",
            headers: { "Accept": "application/json" },
            signal: postsAbortController.signal,
        });
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

getPosts()
