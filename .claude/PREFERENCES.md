# MetricsHour - Development Preferences

## Code Style

### Python
- PEP 8 strictly (use black formatter if available)
- Type hints on all function signatures: `def get_country(code: str) -> Country:`
- Descriptive names: `user_email` not `ue`, `country_list` not `cl`
- Docstrings only for complex functions (not self-explanatory ones)
- Max line length: 100 characters

### JavaScript/Vue
- Composition API only (not Options API)
- Single quotes for strings: `'hello'` not `"hello"`
- Trailing commas: `{ name: 'test', }` ← yes that comma
- Descriptive const names: `const countries = []` not `const c = []`
- Never use `var` (use `const`/`let`)

### Comments
- Explain WHY not WHAT
- Only for non-obvious logic
- Bad: `// Loop through users` (obvious)
- Good: `// Skip deleted users to avoid showing in public feed` (explains why)

## Git Workflow

### Commit messages (semantic)
- `feat: add CSV export to Pro tier`
- `fix: Germany page 500 error on missing GDP data`
- `docs: update README with deployment steps`
- `style: format code with black`
- `refactor: extract trade calculation into helper`

### Before every commit
- Run `git status` (show what's changed)
- Never commit `.env` files
- Never commit API keys or secrets

## Communication Style

- Show code, don't just describe: "Here's the function" + code block
- Show actual errors: full stack trace, not "there was an error"
- If multiple approaches, explain tradeoffs: "Option A is faster but uses more memory"
- Before running commands: tell me what you're about to do and show the actual command
- Wait for confirmation on destructive operations (database drops, deletes)

## Testing & Deployment

- Always test locally first: `npm run dev` (frontend), `uvicorn main:app --reload` (backend)
- Never deploy untested code
- Deployment order: test locally → commit to git → tell me what changed → wait for "deploy" command → verify after deploy

## Security Rules

### Never
- Hardcode secrets in code
- Commit API keys
- Store passwords in plain text
- Trust user input without validation
- Use string concatenation for SQL (always use ORM)

### Always
- Hash passwords with Argon2
- Use parameterized queries (SQLAlchemy ORM does this)
- Validate all API inputs
- Set CORS headers properly
- Log errors (but never log passwords/tokens)

## Error Handling

### Logging
- All errors → `/var/log/metricshour/error.log`
- Include: timestamp, user_id (if available), full stack trace
- Never log passwords, API keys, or PII

### User-facing errors
- Generic to user: "Something went wrong, please try again"
- Detailed in logs: full error with context
- Proper status codes: 400, 401, 404, 500

## SEO Content Requirements

- 800-1000 words minimum
- Use REAL data from OUR database (not made up examples)
- Cite with dates: "According to World Bank data (February 2026)…"
- Target long-tail keywords: "how us china trade affects tech stocks" not just "trade"
- Include 3-5 internal links to our pages
- NO generic AI phrases like "it's important to note that" or "in conclusion"

## Performance Targets

### Frontend
- Page load: <1 second
- Lighthouse score: >90
- Mobile-first (most users are mobile)

### Backend
- API response: <200ms average
- Database queries: use `EXPLAIN ANALYZE` if >100ms
- Cache everything possible (Redis)

## Don't Ask Permission For
- Fixing obvious bugs
- Adding error handling
- Improving code formatting
- Adding helpful comments

## Don't Do
- Over-engineer (simple > complex always)
- Add npm packages when vanilla works
- Redesign working features without asking first
- Write 500-line functions (break them up)

## File Management

- **Development:** `/root/metricshour/`
- **Production:** `/var/www/metricshour/` — never edit directly, use `git pull`
- **Backups:** `/root/backups/` AND Cloudflare R2 — always backup database before schema changes

## Memory System

### When to update memory files
- After completing a feature → update `PROGRESS.md`
- After making architectural decision → update `CONTEXT.md`
- If preferences change → update this file (`PREFERENCES.md`)
- When told "update memory" → update relevant file

### Session start
- Read all 4 memory files at the START of every session
- Say "Memory loaded ✓" after reading
- Then ask what we're working on today
