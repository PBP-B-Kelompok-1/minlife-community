// retrieve data embedded in referrer <script>
const scriptElem = document.currentScript;
const GET_POSTS_ENDPOINT = scriptElem.dataset.getPostsEndpoint;

const postsContainer = document.getElementById("posts");
let postsAbortController;
async function getPosts() {
    if (postsAbortController) postsAbortController.abort();
    postsAbortController = new AbortController();
    try {
        const response = await fetch(GET_POSTS_ENDPOINT, {
            method: "GET",
            headers: { "Accept": "application/json" },
            signal: postsAbortController.signal,
        });
        const data = (await response.json()).data;

        if (data.length === 0) {
            statusElem
        } else {

            data.forEach(post => {

            });
        }
    } catch (error) {
        if (error.name == 'AbortError') return;
        console.error(`An error occured: ${error}`);
        statusElem
    }
}
