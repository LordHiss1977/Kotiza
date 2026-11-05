# Kotiza — bottom-up construction cost estimating

Kotiza builds contract prices from the ground up: **labor and material costs → crews → tasks → indirect costs → markups → contract price**. All rates and costs live in a local SQLite database.

## Run it

You need Python 3.9 or newer. There's nothing else to install.

```bash
python3 -m kotiza
```

Then open <http://127.0.0.1:8000>. On first launch it creates `kotiza.db` next to the `kotiza/` folder and loads sample data (Panama-style USD rates) plus a sample estimate. Both are there to show how things work; replace them with your own.

Options: `--port 8080`, `--host 0.0.0.0` (lets other people on your network use it), `--db /path/to/file.db`. You can also set the `KOTIZA_DB` environment variable instead of `--db`.

## How a price is built

| Level | What it holds | How it's costed |
|---|---|---|
| **Labor** | Trades with a base hourly wage + burden % (social charges, benefits, 13th month…) | Loaded rate = base × (1 + burden%) |
| **Equipment** | Machines with an hourly cost (ownership/rental + operating) | $/hr |
| **Materials & consumables** | Unit cost, unit of measure, waste % | qty × (1 + waste%) × unit cost |
| **Crews** | A mix of labor trades and equipment | Crew $/hr = Σ labor loaded rates + Σ equipment rates |
| **Tasks** | A measured work item: unit of measure, quantity, crew, production rate (units per crew-day), materials and consumables per unit | See below |
| **Indirect costs** | Site staff, facilities, mobilization, insurance, small tools… | Quantity × rate (e.g. 3 months × $3,500), **or** % of direct cost, **or** % of direct labor |
| **Markups** | Contingency, overhead, profit, bonds, tax | Each one is applied to the running total, in that order |

**Task cost** (quantity *Q*):

```
crew-days   = Q ÷ production rate
crew-hours  = crew-days × working hours/day
labor       = crew-hours × crew labor $/hr
equipment   = crew-hours × crew equipment $/hr
materials   = Σ Q × qty/unit × (1 + waste%) × unit cost
consumables = same, for items flagged "consumable"
direct      = labor + equipment + materials + consumables
unit cost   = direct ÷ Q
```

**Contract price:**

```
total cost        = direct + indirect
price before tax  = cost × (1+contingency) × (1+overhead) × (1+profit) × (1+bond)
contract price    = price before tax × (1 + tax)
```

**Bid unit prices:** the price before tax is spread across the tasks in proportion to each task's direct cost. K = price before tax ÷ direct cost, and each bid unit price = unit cost × K. The bill of quantities therefore adds up exactly to the subtotal before tax.

## Workflow

1. **Database:** set up labor, equipment, materials/consumables, and crews. Optionally, build standard tasks in the **Task library** and standard items in the **Indirects** library.
2. **Estimates → New estimate:** enter project details and working hours per day.
3. **Add tasks:** pick a standard task and enter its quantity, or use **Build a new task** (choose the unit, quantity, crew, and production rate, then add materials and consumables per unit). The editor shows the unit cost live as you type. To reuse a task you built, use **Save + copy to library** in the task editor.
4. **Add indirect costs** from the library or as blank lines.
5. **Set markups** in the summary panel. The contract price, K factor, and indicators update as you go.
6. **Report / print:** a client bill of quantities, plus an optional internal cost build-up and unit-price analysis per task. Use the browser's Print → Save as PDF. **Export CSV** opens in Excel.

### How prices update

- An estimate uses **live database prices**. If you change a wage, material cost, or crew, every estimate that uses it is recalculated. To freeze a submitted estimate, keep a PDF/CSV of it, or use **Duplicate** before you change rates.
- Adding a task from the library **copies** it into the estimate. Editing the task inside the estimate does not change the library, and editing the library does not change estimates.
- You can't delete a resource that a crew, task, or estimate still uses. The app tells you when this happens.

## Project layout

```
kotiza/db.py         schema + sample data (SQLite)
kotiza/calc.py       cost engine (pure functions) + database loaders
kotiza/server.py     JSON API + static file server (standard library only)
kotiza/static/       browser UI (HTML/CSS/vanilla JS, no build step)
tests/               unit + API tests
```

Run the tests with:

```bash
python3 -m unittest discover -s tests -v
```

Back up your data by copying `kotiza.db`.
