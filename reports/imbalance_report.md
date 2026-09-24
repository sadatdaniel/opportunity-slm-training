# Category / Source Imbalance Report

Corpus v1: 3296 canonical records from 16 sources.
Category figures use weak title signals only (labels come from the teacher pilot)
and lower-bound true coverage; they identify clearly starved classes.

## Signal-based category coverage

| category | candidates | share of corpus |
|---|---|---|
| scholarships | 683 | 20.7% |
| fellowships | 370 | 11.2% |
| grants | 149 | 4.5% |
| workshops | 125 | 3.8% |
| internships | 120 | 3.6% |
| phd | 104 | 3.2% |
| awards | 90 | 2.7% |
| conferences | 80 | 2.4% |
| competitions | 51 | 1.5% |
| exchange_programs | 8 | 0.2% |
| postdoc | 2 | 0.1% |
| miscellaneous | 0 | 0.0% |
| (no type signal in title) | 1514 | 45.9% |

## Source distribution

| source | records | share |
|---|---|---|
| opportunities_for_youth | 597 | 18.1% |
| opportunity_desk | 589 | 17.9% |
| scholars4dev | 468 | 14.2% |
| association_of_african_universities_aau | 465 | 14.1% |
| opportunities_circle | 351 | 10.6% |
| barcelona_institute_of_science_and_technology_bist | 243 | 7.4% |
| paset_rsif | 183 | 5.6% |
| mit_graduate_fellowships_pappalardo | 109 | 3.3% |
| woods_hole_oceanographic_institution_whoi | 102 | 3.1% |
| european_science_foundation_esf | 82 | 2.5% |
| ihes | 54 | 1.6% |
| fulbright_nehru_opportunities_us_india | 37 | 1.1% |
| commonwealth_scholarship_commission | 9 | 0.3% |
| inomics | 4 | 0.1% |
| asia_europe_foundation_asef | 2 | 0.1% |
| open_society_foundations_osf | 1 | 0.0% |

## Collection guidance (model-driven, brief step 8)

- Likely underrepresented: competitions, exchange_programs, miscellaneous, postdoc — preferential collection once measured.
- Largest source holds 18% of the corpus; source-aware splits and the unseen-source holdout (already in build_dataset) guard against overfitting it.
