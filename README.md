
# HawkLens

**Building intelligence for smarter, lower-carbon real estate investments.**

HawkLens is a building analysis and retrofit planning platform that brings property information, visual inspections, sustainability goals, and financial planning into one interface.

It helps users explore a portfolio, assess potential upgrades, and understand the tradeoffs between cost, carbon reduction, and projected value.

> **Demo Notice:** HawkLens includes illustrative calculations and demo workflows. Estimates are not investment advice or verified engineering assessments. Features and integrations may differ between branches.

## The Problem

Commercial property owners face a difficult challenge: improving
building efficiency while managing costs, investment returns,
and sustainability commitments.

The information needed to make these decisions is often
fragmented across property records, building inspections,
energy data, and financial models.

Even when potential upgrades are identified, it can be
difficult to determine which improvements deliver the
greatest value within a limited budget.

## Our Solution

HawkLens brings building intelligence and investment planning
into a single platform.

By connecting property information, visual building
exploration, AI-assisted analysis workflows, carbon targets,
and financial modeling, HawkLens helps users move from
understanding a building to evaluating an actionable
retrofit strategy.

Our platform is designed to answer three questions:

1. **What can we improve?**
   Identify potential building efficiency upgrades using
   available property information and survey evidence.

2. **What impact could it have?**
   Explore estimated energy savings, carbon reductions,
   and potential improvements across a property portfolio.

3. **Is it worth the investment?**
   Evaluate estimated costs, financial assumptions, and
   competing retrofit opportunities.

## What Makes HawkLens Different

### Building Intelligence Meets Financial Intelligence

HawkLens connects technical building analysis with
real estate investment planning.

Rather than simply identifying inefficient buildings,
the platform helps users explore which interventions
could deliver meaningful environmental and financial value.

### Portfolio-Level Decision Making

Property owners can evaluate buildings within a broader
portfolio and explore carbon reduction targets alongside
investment considerations.

### Visual, Evidence-Oriented Workflows

Matterport 3D tours, property information, survey screens,
and supporting evidence help users explore the context
behind potential retrofit recommendations.

### AI-Assisted Analysis Architecture

HawkLens uses a Python and FastAPI backend with
LangGraph, Google Gen AI, and supporting analysis tools
to provide a foundation for coordinated building
assessment workflows.

### From Recommendations to Action

HawkLens connects retrofit opportunities to planning,
financial assumptions, and investment documentation.

## Our Vision

We believe sustainability decisions should be easier
to understand, evaluate, and act on.

Our long-term vision is to make building intelligence
accessible across entire real estate portfolios,
helping owners prioritize improvements that reduce
emissions while supporting stronger financial decisions.

**HawkLens makes smarter buildings a smarter investment.**

---

## Features

- **Portfolio Dashboard:** Browse a Houston property portfolio with building images and Matterport 3D tours.
- **Building Exploration:** Open property details and inspect supporting building information.
- **Carbon Goal Planning:** Adjust reduction targets and explore estimated investment and carbon impacts.
- **Retrofit Recommendations:** Review potential improvements such as lighting, rooftop solar, and HVAC upgrades.
- **Survey Workflow:** Navigate survey initiation, progress, results, and supporting evidence screens.
- **Financial Planning:** Explore investment plans, assumptions, financing, and funding-related demo screens.
- **Documents:** Access investment memos and document-oriented views.
- **Interface Enhancements:** Topographic background, Change theme, and a command palette with property search. 

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, Vite, React Router, Tailwind CSS |
| Backend | Python, FastAPI, Uvicorn |
| AI Orchestration | LangGraph, LangChain Core, Google Gen AI |
| Data & Geometry | NumPy, Shapely, PyProj |
| Optimization | PuLP |
| Testing | Pytest, pytest-asyncio |
| 3D Property Viewing | Matterport |

---

## Project Structure

```text
HawkLens/
├── frontend/
│   ├── src/
│   │   ├── components/     # Shared UI components
│   │   ├── pages/          # Portfolio, survey, plan, and other screens
│   │   ├── lib/            # Shared frontend logic
│   │   └── App.jsx         # Routes and application providers
│   └── package.json
├── backend/
│   └── requirements.txt
└── README.md
```

---

## Getting Started

### Prerequisites

Make sure you have the following installed:

- Node.js and npm
- Python and pip (compatible with backend dependencies)
- Any API keys or services required by the backend workflows you intend to run

### 1. Clone the Repository

```bash
git clone https://github.com/Samvidab/HawkLens.git
cd HawkLens
```

### 2. Run the Frontend

From the repository root:

```bash
cd frontend
npm install
npm run dev
```

Open the URL

**https://hawklens.vip/**

To create a production build:

```bash
npm run build
```

### 3. Run the Backend

Open a new terminal and navigate to the backend directory:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The backend uses FastAPI and Uvicorn.

Start it using the application module for your checked-out branch:

```bash
uvicorn <module_name>:app --reload
```

Replace `<module_name>` with the actual Python module that defines your FastAPI application.

Configure any required environment variables before running external integrations.

---

## How to Use

### 1. Explore the Portfolio

Open the dashboard to browse available buildings, view property information, and launch Matterport 3D tours.

### 2. Set a Carbon Goal

Adjust the target carbon reduction percentage to explore modeled impacts across the portfolio.

### 3. Review Retrofit Opportunities

Inspect potential building improvements, including:

- HVAC upgrades
- Energy-efficient lighting
- Rooftop solar
- Building envelope improvements

Review estimated costs, projected savings, and supporting information where available.

### 4. Explore the Survey Workflow

Navigate through the survey process:

1. Start a building survey.
2. View survey progress.
3. Review survey results.
4. Inspect supporting evidence.

Some survey statuses and outputs may be simulated for demonstration purposes.

### 5. Evaluate the Investment Plan

Explore financial assumptions, potential investment scenarios, funding-related workflows, and supporting documents.

---

## Interface Enhancements

Development branches may include additional interactive features.

### Mission Control

Switch between the standard dashboard and a dark monitoring interface designed for a more technical viewing experience.

### Command Palette

Use the keyboard shortcut:

- **macOS:** `Cmd + K`
- **Windows/Linux:** `Ctrl + K`

Search application pages and, when connected to the backend, available properties.

Select a property to open its Matterport tour.

### Topographic Background

A subtle animated contour-line background adds visual depth around the main dashboard while maintaining a clean interface.

---

## Architecture Overview

```text
                  HawkLens
                      |
                      v
             React + Vite Frontend
                      |
                      | API Requests
                      v
               FastAPI Backend
                      |
          +-----------+-----------+
          |           |           |
          v           v           v
       Survey      AI Agent    Financial &
      Workflows   Orchestration Optimization
          |           |           |
          |       LangGraph       PuLP
          |       Google Gen AI   NumPy
          |                       |
          +-----------+-----------+
                      |
                      v
              Analysis Results
                      |
                      v
              HawkLens Dashboard
```

Matterport tours are displayed in the frontend where available.

The interface includes demo screens and modeled values. Not every displayed status or calculation is necessarily driven by a live backend operation.

---

## Development Notes

- Keep API keys and credentials out of source control.
- Use environment variables for external integrations.
- Treat synthetic data and illustrative forecasts as demonstrations unless validated against live sources.
- Preserve the existing route structure in `frontend/src/App.jsx` when adding components.
- Clearly distinguish simulated survey progress from real backend events.

---

## Roadmap

Future improvements include:

- [ ] Connect survey progress indicators to live agent events.
- [ ] Improve property search and individual 3D tour navigation.
- [ ] Add evidence-backed, property-specific retrofit recommendations.
- [ ] Expand financial scenario comparisons.
- [ ] Add exportable investment summaries.
- [ ] Improve real-time building intelligence and analysis.
- [ ] Expand portfolio-level sustainability reporting.

---

## Disclaimer

HawkLens is a prototype built to demonstrate how building intelligence, sustainability analysis, and financial planning can work together.

Any carbon savings, retrofit costs, or investment returns shown in the demo are illustrative and should be independently verified before real-world use.

HawkLens does not provide professional engineering, financial, or investment advice.
