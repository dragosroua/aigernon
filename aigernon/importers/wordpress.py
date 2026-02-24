"""WordPress GraphQL importer."""

import asyncio
from typing import Callable, Any

from aigernon.importers.base import BaseImporter, ImportResult
from aigernon.memory.vector import VectorStore
from aigernon.memory.chunker import TextChunker


class WordPressImporter(BaseImporter):
    """
    Import posts from WordPress via GraphQL API.

    Supports WPGraphQL plugin endpoints.
    """

    DEFAULT_BATCH_SIZE = 100

    def __init__(
        self,
        vector_store: VectorStore,
        collection: str = "blog",
        chunker: TextChunker | None = None,
        on_progress: Callable[[int, int, str], None] | None = None,
    ):
        super().__init__(vector_store, collection, chunker, on_progress)

    def import_all(
        self,
        graphql_url: str,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_posts: int | None = None,
        categories: list[str] | None = None,
    ) -> ImportResult:
        """
        Import all posts from WordPress via GraphQL.

        Args:
            graphql_url: WordPress GraphQL endpoint URL
            batch_size: Number of posts to fetch per request
            max_posts: Maximum posts to import (None = all)
            categories: Optional list of category slugs to filter

        Returns:
            ImportResult with statistics
        """
        return asyncio.run(
            self._import_all_async(graphql_url, batch_size, max_posts, categories)
        )

    async def _import_all_async(
        self,
        graphql_url: str,
        batch_size: int,
        max_posts: int | None,
        categories: list[str] | None,
    ) -> ImportResult:
        """Async implementation of import_all."""
        import httpx

        result = ImportResult(success=True)
        cursor = None
        posts_imported = 0

        async with httpx.AsyncClient(timeout=60.0) as client:
            while True:
                # Fetch batch
                try:
                    posts, next_cursor, total = await self._fetch_posts(
                        client,
                        graphql_url,
                        batch_size,
                        cursor,
                        categories,
                    )
                except Exception as e:
                    result.errors.append(f"Fetch error: {str(e)}")
                    result.success = False
                    break

                if not posts:
                    break

                # Process posts
                for post in posts:
                    if max_posts and posts_imported >= max_posts:
                        break

                    try:
                        chunks_created = self._import_post(post)
                        result.documents_processed += 1
                        result.chunks_created += chunks_created
                        posts_imported += 1

                        self._report_progress(
                            posts_imported,
                            total or posts_imported,
                            f"Imported: {post.get('title', 'Untitled')[:50]}",
                        )

                    except Exception as e:
                        result.errors.append(f"{post.get('slug', 'unknown')}: {str(e)}")

                if max_posts and posts_imported >= max_posts:
                    break

                if not next_cursor:
                    break

                cursor = next_cursor

        return result

    async def _fetch_posts(
        self,
        client: Any,
        graphql_url: str,
        batch_size: int,
        cursor: str | None,
        categories: list[str] | None,
    ) -> tuple[list[dict], str | None, int | None]:
        """
        Fetch a batch of posts from WordPress GraphQL.

        Returns:
            Tuple of (posts, next_cursor, total_count)
        """
        # Build GraphQL query
        query = """
        query GetPosts($first: Int!, $after: String, $categoryIn: [ID]) {
            posts(first: $first, after: $after, where: {categoryIn: $categoryIn}) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                nodes {
                    id
                    databaseId
                    title
                    slug
                    uri
                    content
                    date
                    modified
                    categories {
                        nodes {
                            name
                            slug
                        }
                    }
                    tags {
                        nodes {
                            name
                            slug
                        }
                    }
                }
            }
        }
        """

        variables = {
            "first": batch_size,
            "after": cursor,
        }

        if categories:
            variables["categoryIn"] = categories

        response = await client.post(
            graphql_url,
            json={"query": query, "variables": variables},
        )
        response.raise_for_status()

        data = response.json()

        if "errors" in data:
            raise Exception(f"GraphQL errors: {data['errors']}")

        posts_data = data.get("data", {}).get("posts", {})
        nodes = posts_data.get("nodes", [])
        page_info = posts_data.get("pageInfo", {})

        next_cursor = page_info.get("endCursor") if page_info.get("hasNextPage") else None

        return nodes, next_cursor, None

    def _import_post(self, post: dict) -> int:
        """
        Import a single WordPress post.

        Args:
            post: Post data from GraphQL

        Returns:
            Number of chunks created
        """
        content = post.get("content", "")
        if not content:
            return 0

        # Extract categories and tags
        categories = [
            cat.get("slug", "")
            for cat in post.get("categories", {}).get("nodes", [])
        ]
        tags = [
            tag.get("slug", "")
            for tag in post.get("tags", {}).get("nodes", [])
        ]

        # Build metadata
        metadata = {
            "source": "wordpress",
            "post_id": post.get("databaseId"),
            "title": post.get("title", ""),
            "slug": post.get("slug", ""),
            "url": post.get("uri", ""),
            "date": post.get("date", ""),
            "modified": post.get("modified", ""),
            "categories": categories,
            "tags": tags,
        }

        # Use blog post chunker
        chunks = self.chunker.chunk_blog_post(
            content=content,
            title=post.get("title", ""),
            url=post.get("uri", ""),
            date=post.get("date", ""),
            tags=tags,
            categories=categories,
        )

        # Generate stable ID from post ID
        base_id = f"wp_{post.get('databaseId', post.get('slug', 'unknown'))}"

        return self._index_chunks(chunks, base_id)

    def import_post(
        self,
        graphql_url: str,
        slug: str,
    ) -> ImportResult:
        """
        Import a single post by slug.

        Args:
            graphql_url: WordPress GraphQL endpoint URL
            slug: Post slug

        Returns:
            ImportResult with statistics
        """
        return asyncio.run(self._import_post_async(graphql_url, slug))

    async def _import_post_async(
        self,
        graphql_url: str,
        slug: str,
    ) -> ImportResult:
        """Async implementation of import_post."""
        import httpx

        result = ImportResult(success=True)

        query = """
        query GetPostBySlug($slug: ID!) {
            post(id: $slug, idType: SLUG) {
                id
                databaseId
                title
                slug
                uri
                content
                date
                modified
                categories {
                    nodes {
                        name
                        slug
                    }
                }
                tags {
                    nodes {
                        name
                        slug
                    }
                }
            }
        }
        """

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    graphql_url,
                    json={"query": query, "variables": {"slug": slug}},
                )
                response.raise_for_status()

                data = response.json()
                if "errors" in data:
                    raise Exception(f"GraphQL errors: {data['errors']}")

                post = data.get("data", {}).get("post")
                if not post:
                    result.success = False
                    result.errors.append(f"Post not found: {slug}")
                    return result

                result.chunks_created = self._import_post(post)
                result.documents_processed = 1

            except Exception as e:
                result.success = False
                result.errors.append(str(e))

        return result
