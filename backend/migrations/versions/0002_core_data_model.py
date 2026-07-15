"""Core data model: orgs, users, installations, repositories, capabilities, tasks, runs, audit

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-15

"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE organizations (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            github_org_id BIGINT NOT NULL UNIQUE,
            login TEXT NOT NULL,
            name TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE users (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            external_auth_id TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL,
            github_login TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE organization_members (
            organization_id BIGINT NOT NULL
                REFERENCES organizations(id) ON DELETE CASCADE,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role TEXT NOT NULL DEFAULT 'member'
                CHECK (role IN ('admin', 'member')),
            PRIMARY KEY (organization_id, user_id)
        );

        CREATE TABLE installations (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            github_installation_id BIGINT NOT NULL UNIQUE,
            organization_id BIGINT NOT NULL
                REFERENCES organizations(id) ON DELETE CASCADE,
            installed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            suspended_at TIMESTAMPTZ
        );

        CREATE TABLE repositories (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            github_repo_id BIGINT NOT NULL UNIQUE,
            installation_id BIGINT NOT NULL
                REFERENCES installations(id) ON DELETE CASCADE,
            full_name TEXT NOT NULL,
            default_branch TEXT NOT NULL DEFAULT 'main',
            private BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_repositories_full_name ON repositories(full_name);

        CREATE TABLE capability_configs (
            repository_id BIGINT NOT NULL
                REFERENCES repositories(id) ON DELETE CASCADE,
            capability TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'off'
                CHECK (mode IN ('autopilot', 'assisted', 'off')),
            enabled BOOLEAN NOT NULL DEFAULT FALSE,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (repository_id, capability)
        );

        CREATE TABLE tasks (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            repository_id BIGINT NOT NULL
                REFERENCES repositories(id) ON DELETE CASCADE,
            capability TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'triggered'
                CHECK (state IN ('triggered', 'queued', 'planning', 'executing',
                                 'pr_open', 'merged', 'rejected', 'failed')),
            trigger TEXT NOT NULL,
            title TEXT NOT NULL,
            pr_number INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_tasks_repository_state ON tasks(repository_id, state);

        CREATE TABLE runs (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            task_id BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at TIMESTAMPTZ,
            outcome TEXT CHECK (outcome IN ('success', 'failure', 'cancelled')),
            log_uri TEXT,
            tokens_used BIGINT
        );
        CREATE INDEX idx_runs_task ON runs(task_id);

        CREATE TABLE audit_events (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            organization_id BIGINT REFERENCES organizations(id) ON DELETE SET NULL,
            repository_id BIGINT REFERENCES repositories(id) ON DELETE SET NULL,
            task_id BIGINT REFERENCES tasks(id) ON DELETE SET NULL,
            actor TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_audit_events_org_created
            ON audit_events(organization_id, created_at);
        CREATE INDEX idx_audit_events_repo_created
            ON audit_events(repository_id, created_at);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE audit_events;
        DROP TABLE runs;
        DROP TABLE tasks;
        DROP TABLE capability_configs;
        DROP TABLE repositories;
        DROP TABLE installations;
        DROP TABLE organization_members;
        DROP TABLE users;
        DROP TABLE organizations;
        """
    )
