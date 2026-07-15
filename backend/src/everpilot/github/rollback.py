"""One-click rollback: open a revert PR for an Everpilot-merged change (roadmap M2)."""

import logging

from everpilot.github.auth import GitHubAppClients

logger = logging.getLogger(__name__)

_PR_NODE_ID_QUERY = """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) { id }
  }
}
"""

_REVERT_MUTATION = """
mutation($input: RevertPullRequestInput!) {
  revertPullRequest(input: $input) {
    revertPullRequest { number url }
  }
}
"""


class RollbackError(Exception):
    pass


class RollbackService:
    def __init__(self, clients: GitHubAppClients) -> None:
        self._clients = clients

    async def revert_pr(
        self,
        *,
        github_installation_id: int,
        repo_full_name: str,
        pr_number: int,
        reason: str,
    ) -> int:
        """Open a revert PR; returns its number. The revert PR itself is reviewed
        by a human — rollback never auto-merges."""
        owner, _, repo = repo_full_name.partition("/")
        github = self._clients.installation(github_installation_id)

        data = await github.async_graphql(
            _PR_NODE_ID_QUERY, {"owner": owner, "repo": repo, "number": pr_number}
        )
        pull_request = (data.get("repository") or {}).get("pullRequest")
        if not pull_request:
            raise RollbackError(f"PR #{pr_number} not found in {repo_full_name}")

        result = await github.async_graphql(
            _REVERT_MUTATION,
            {
                "input": {
                    "pullRequestId": pull_request["id"],
                    "title": f"Revert: Everpilot PR #{pr_number}",
                    "body": f"Automated rollback requested via Everpilot. Reason: {reason}",
                }
            },
        )
        revert = ((result.get("revertPullRequest") or {}).get("revertPullRequest")) or {}
        number = revert.get("number")
        if number is None:
            raise RollbackError(f"GitHub did not return a revert PR for #{pr_number}")
        logger.info("Opened revert PR #%s for %s#%s", number, repo_full_name, pr_number)
        return number
