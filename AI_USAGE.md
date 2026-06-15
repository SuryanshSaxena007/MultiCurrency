# AI usage

## Tools used

- Sisyphus agent workflow for implementation planning, code generation and verification.
- Librarian sub-agent for framework practice sanity checks.
- Frontend UI/UX skill guidance for the React interface direction.

## Where AI accelerated delivery

- Translating the challenge brief into a scoped FastAPI/React architecture.
- Drafting boilerplate for Docker, CI, typed schemas and docs.
- Generating integration tests around the core wallet flows.

## Where AI suggestions were rejected or constrained

- Avoided adding unnecessary services such as Kafka or Redis to the MVP implementation.
- Avoided binary photo upload because object storage would distract from core wallet correctness.
- Kept migrations out of the implementation while documenting Alembic as the production path.
- Used deterministic fallback exchange rates so review does not depend on third-party uptime.
