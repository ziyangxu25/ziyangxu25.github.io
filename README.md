# ziyangxu25.github.io

Source for my personal academic website, hosted at [ziyangxu25.github.io](https://ziyangxu25.github.io).

Built with [Jekyll](https://jekyllrb.com/) using the [al-folio](https://github.com/alshedivat/al-folio) theme (MIT licensed, see [LICENSE](LICENSE)).

## Local development

```bash
bundle install
bundle exec jekyll serve
```

## Structure

- `_pages/` — site pages (about, publications, CV, blog, etc.)
- `_bibliography/papers.bib` — publications list
- `_data/` — CV, socials, coauthors, venues
- `_news/` — news items shown on the home page
- `bin/update_scholar_citations.py`, `bin/update_scholar_publications.py` — scripts run by scheduled GitHub Actions to sync citation counts and new publications from Google Scholar

## Deployment

Pushing to `main` triggers `.github/workflows/deploy.yml`, which builds the site with Jekyll and publishes it via GitHub Pages.
