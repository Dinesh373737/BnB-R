# GridMind

Autonomous Multi-Agent AI for Resilient Microgrid Coordination.

## Architecture

GridMind follows a strict modular architecture with a shared foundation:

- `backend/common/`: Shared database models, schemas, events, config, and API registry. **(Do not modify during feature development)**
- `backend/modules/`: Isolated feature modules (e.g., agents, forecasting, simulation).
- `frontend/`: React/Next.js dashboard (Built independently).

## Setup

1. Copy `.env.example` to `.env` and fill in the values.
2. Install dependencies: `pip install -r requirements.txt`
3. Initialize the database: `python -m backend.common.init_db`
4. Run the backend: `uvicorn backend.main:app --reload --port 8000`
