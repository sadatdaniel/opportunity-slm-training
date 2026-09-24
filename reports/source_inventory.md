# Source Inventory

Probed 106 of 106 registered sources. Machine-readable results: `data/inventory.json`.

## Recommended collection methods

| method | sources |
|---|---|
| html | 54 |
| needs_manual_review | 17 |
| wp_rest | 14 |
| blocked_document | 14 |
| rss | 7 |

## Per-source results

| source | domain | method | API | posts | feed | robots | notes |
|---|---|---|---|---|---|---|---|
| 10times | 10times.com | blocked_document | refused/- | - | - | false | 403; api:robots.txt disallows https://10times.com |
| academic_gates | academicgates.com | html | refused/- | - | - | true | api:robots.txt disallows https://www.academicgates.com/api/v1/jo |
| academic_positions | academicpositions.com | html | error/- | - | - | true | api:client error (url=https://academicpositions.com/api/v1/jobs, |
| academic_transfer | academictransfer.com | html | error/- | - | - | true | JS-rendered:nuxt; api:client error (url=https://www.academictransfer.com/api/vac |
| academicjobsonline | academicjobsonline.org | needs_manual_review | html/200 | - | - | true |  |
| african_academy_of_sciences_aas | aasciences.africa | needs_manual_review | error/- | - | - | true | api:client error (url=https://aasciences.africa/api/v1/grants, s |
| african_scholar_initiative | scholarshipsforafricans.com | html | error/- | - | - | true | api:client error (url=https://scholarshipsforafricans.com/wp-jso |
| after_school_africa | afterschoolafrica.com | html | refused/- | - | - | true | api:robots.txt disallows https://www.afterschoolafrica.com/wp-js |
| alan_turing_institute | turing.ac.uk | needs_manual_review | error/- | - | - | true | api:client error (url=https://www.turing.ac.uk/jsonapi/node/oppo |
| alexander_von_humboldt_foundation | humboldt-foundation.de | html | error/- | - | - | true | api:client error (url=https://www.humboldt-foundation.de/jsonapi |
| armacad | armacad.info | html | error/- | - | - | true | api:client error (url=https://armacad.info/api/v1/announcements, |
| asia_europe_foundation_asef | asef.org | wp_rest | wp_rest/200 | yes | - | true |  |
| association_of_african_universities_aau | blog.aau.org | wp_rest | wp_rest/200 | yes | rss | true |  |
| australia_awards | dfat.gov.au | html | error/- | - | - | true | api:client error (url=https://www.dfat.gov.au/api/content, statu |
| australian_national_university_anu | anu.edu.au | html | error/- | - | - | true | api:client error (url=https://www.anu.edu.au/api/scholarships/se |
| barcelona_institute_of_science_and_technology_bist | bist.eu | wp_rest | wp_rest/200 | yes | rss | true |  |
| caldo_consortium | caldo.ca | blocked_document | refused/- | - | - | false | 403; api:robots.txt disallows https://caldo.ca/wp-json/wp/v2/pages |
| cambridge_university_gates_cambridge | gatescambridge.org | wp_rest | wp_rest/200 | - | rss | true |  |
| campus_austria_oead | grants.at | html | error/- | - | - | true | JS-rendered:ng-app; api:client error (url=https://grants.at/api/v1/scholarships, |
| campus_france_eiffel_excellence | doctorat.campusfrance.org | html | error/- | - | - | true | api:client error (url=https://doctorat.campusfrance.org/api/offe |
| cern_careers_studentships | careers.cern | rss | refused/- | - | rss | true | api:robots.txt disallows https://api.smartrecruiters.com/v1/comp |
| chevening_scholarships | chevening.org | rss | error/- | - | rss | true | api:client error (url=https://www.chevening.org/wp-json/wp/v2/pa |
| china_scholarship_council_csc | campuschina.org | blocked_document | refused/- | - | - | false | 403; api:robots.txt disallows https://www.campuschina.org |
| cnrs | emploi.cnrs.fr | blocked_document | error/- | - | - | true | 403; api:client error (url=https://emploi.cnrs.fr/api/Offres, status= |
| columbia_university_graduate_school | grad.columbia.edu | needs_manual_review | error/- | - | - | true | api:gave up after 3 attempts: network error: [Errno 11001] getad |
| commonwealth_scholarship_commission | cscuk.fcdo.gov.uk | rss | html/200 | - | rss | true |  |
| conference_alert | conferencealerts.com | html | error/- | - | - | true | api:client error (url=https://conferencealerts.com/api/events, s |
| council_of_american_overseas_research_centers_caorc | caorc.org | html | error/- | - | - | true | api:client error (url=https://www.caorc.org/wp-json/wp/v2/posts, |
| daad_german_academic_exchange_service | www2.daad.de | html | error/- | - | - | true | api:client error (url=https://www.daad.de/api/scholarships/v1/en |
| erasmus_erasmus_mundus_joint_masters | erasmus-plus.ec.europa.eu | html | html/200 | - | - | true |  |
| eth_zurich_doctorate_fellowships | ethz.ch | html | error/- | - | - | true | api:client error (url=https://ethz.ch/bin/ethz/news/api.json, st |
| euraxess | euraxess.ec.europa.eu | html | refused/- | - | - | true | api:robots.txt disallows https://euraxess.ec.europa.eu/api/jobs/ |
| european_molecular_biology_laboratory_embl | embl.org | html | error/- | - | - | true | api:client error (url=https://www.embl.org/wp-json/wp/v2/posts,  |
| european_science_foundation_esf | esf.org | wp_rest | wp_rest/200 | yes | - | true |  |
| european_southern_observatory_eso | recruitment.eso.org | html | error/- | - | - | true | api:client error (url=https://recruitment.eso.org/api/v1/jobs, s |
| european_university_institute_eui | eui.eu | html | error/- | - | - | true | api:client error (url=https://www.eui.eu/_api/v2/news/events, st |
| findaphd_findamasters_findapostdoc | findaphd.com | blocked_document | refused/- | - | - | true | 403; api:403 for https://www.findaphd.com/api/search - not retrying |
| flatiron_institute_simons_foundation | simonsfoundation.org | blocked_document | wp_rest/200 | yes | - | true | 403 |
| foundation_for_science_and_technology_fct_portugal | fct.pt | html | error/- | - | - | true | api:client error (url=https://www.fct.pt/jsonapi/node/call, stat |
| fraunhofer_gesellschaft | fraunhofer.de | html | html/200 | - | - | true |  |
| fulbright_nehru_opportunities_us_india | usief.org.in | wp_rest | wp_rest/200 | yes | rss | true |  |
| fulbright_program | fulbrightscholars.org | html | error/- | - | - | true | api:client error (url=https://fulbrightscholars.org/wp-json/wp/v |
| harvard_gsas_harvard_fellowships | gsas.harvard.edu | html | error/- | - | - | true | api:gave up after 3 attempts: network error: [Errno 11001] getad |
| helmholtz_association | helmholtz.de | html | html/200 | - | - | true |  |
| heysuccess | heysuccess.com | html | error/- | - | - | true | JS-rendered:ng-app; api:gave up after 3 attempts: HTTP 500 (url=https://www.heys |
| human_frontier_science_program_hfsp | hfsp.org | needs_manual_review | error/- | - | - | true | api:client error (url=https://www.hfsp.org/wp-json/wp/v2/posts,  |
| ictp_trieste | ictp.it | needs_manual_review | error/- | - | - | true | api:client error (url=https://www.ictp.it/api/v1/opportunities,  |
| idealist_org | idealist.org | html | html/200 | - | - | true |  |
| ihes | ihes.fr | wp_rest | wp_rest/200 | yes | rss | true |  |
| iiasa | iiasa.ac.at | blocked_document | refused/- | - | - | false | 403; api:robots.txt disallows https://iiasa.ac.at/jsonapi/node/opport |
| inomics | inomics.com | rss | error/- | - | rss | true | api:client error (url=https://inomics.com/api/v1/offers, status= |
| interacademy_partnership_iap | interacademies.org | needs_manual_review | error/- | - | - | true | api:client error (url=https://www.interacademies.org/wp-json/wp/ |
| international_astronomical_union_iau | iau.org | needs_manual_review | error/- | - | - | true | api:client error (url=https://www.iau.org/api/v1/grants, status= |
| irish_research_council_irc | research.ie | html | error/- | - | - | true | api:client error (url=https://research.ie/wp-json/wp/v2/posts, s |
| japan_society_for_the_promotion_of_science_jsps | jsps.go.jp | html | html/200 | - | - | true |  |
| jobs_ac_uk | jobs.ac.uk | html | html/200 | - | - | true |  |
| korean_government_scholarship_kgsp | studyinkorea.go.kr | html | html/200 | - | - | true |  |
| leibniz_association | leibniz-gemeinschaft.de | html | html/200 | - | - | true |  |
| marie_skodowska_curie_actions_msca | marie-sklodowska-curie-actions.ec.europa.eu | html | html/200 | - | - | true |  |
| masterprograms_com | masterprograms.com | needs_manual_review | html/200 | - | - | true |  |
| max_delbruck_center_for_molecular_medicine_mdc_berlin | mdc-berlin.de | html | error/- | - | - | true | api:client error (url=https://www.mdc-berlin.de/jsonapi/node/job |
| max_planck_society_imprs | mpg.de | html | error/- | - | - | true | api:client error (url=https://www.mpg.de/api/jobboard/offers, st |
| mext_scholarship_japan | studyinjapan.go.jp | html | error/- | - | - | true | api:client error (url=https://www.studyinjapan.go.jp/api/v1/scho |
| mina7 | mina7.net | needs_manual_review | error/- | - | - | true | api:gave up after 3 attempts: network error: [SSL: CERTIFICATE_V |
| mit_graduate_fellowships_pappalardo | physics.mit.edu | wp_rest | wp_rest/200 | yes | - | true |  |
| national_research_foundation_nrf_south_africa | nrf.ac.za | needs_manual_review | error/- | - | - | true | api:gave up after 3 attempts: network error: [SSL: CERTIFICATE_V |
| national_university_of_singapore_nus | nusgs.nus.edu.sg | html | html/200 | - | - | true |  |
| nordforsk | nordforsk.org | html | html/200 | - | - | true |  |
| nserc_canada | nserc-crsng.gc.ca | html | error/- | - | - | true | api:client error (url=https://open.canada.ca/data/api/action/pac |
| nuffic_holland_scholarship | studyinnl.org | html | html/200 | - | - | true |  |
| oas_scholarships | oas.org | blocked_document | refused/- | - | - | false | 403; api:robots.txt disallows https://www.oas.org/en/scholarships |
| oist_okinawa_institute_of_science_and_technology | admissions.oist.jp | html | html/200 | - | - | true | JS-rendered:id="root" |
| open_society_foundations_osf | opensocietyfoundations.org | rss | error/- | - | atom | true | api:client error (url=https://www.opensocietyfoundations.org/api |
| opportunities_circle | opportunitiescircle.com | wp_rest | wp_rest/200 | yes | rss | true |  |
| opportunities_for_youth | opportunitiesforyouth.org | wp_rest | wp_rest/200 | yes | rss | true |  |
| opportunity_desk | opportunitydesk.org | wp_rest | wp_rest/200 | yes | rss | true |  |
| paset_rsif | rsif-paset.org | wp_rest | wp_rest/200 | yes | rss | true |  |
| pasteur_institute | pasteur.fr | html | error/- | - | - | true | api:client error (url=https://www.pasteur.fr/en/jsonapi/node/edu |
| perimeter_institute_for_theoretical_physics | perimeterinstitute.ca | html | error/- | - | - | true | api:client error (url=https://perimeterinstitute.ca/wp-json/wp/v |
| princeton_university_society_of_fellows | sf.princeton.edu | blocked_document | refused/- | - | - | true | 403; api:403 for https://sf.princeton.edu/wp-json/wp/v2/pages - not r |
| researchgate_opportunities_platform | researchgate.net | needs_manual_review | error/- | - | - | true | api:client error (url=https://www.researchgate.net/graphql, stat |
| riken | riken.jp | html | html/200 | - | - | true |  |
| santa_fe_institute | santafe.edu | html | html/200 | - | - | true | JS-rendered:id="app" |
| scholars4dev | scholars4dev.com | wp_rest | wp_rest/200 | yes | rss | true |  |
| scholarship_position | scholarship-positions.com | needs_manual_review | html/200 | - | - | true |  |
| seameo | seameo.org | html | error/- | - | - | true | api:client error (url=https://www.seameo.org/wp-json/wp/v2/posts |
| simons_foundation | simonsfoundation.org | blocked_document | wp_rest/200 | yes | - | true | 403 |
| stanford_university_knight_hennessy_scholars | knight-hennessy.stanford.edu | blocked_document | refused/- | - | - | true | 403; api:403 for https://knight-hennessy.stanford.edu/wp-json/wp/v2/p |
| studyportals_scholarshipportal_mastersportal_phdportal | scholarshipportal.com | html | html/200 | - | - | true |  |
| swedish_institute_scholarships | si.se | blocked_document | refused/- | - | - | false | 403; api:robots.txt disallows https://si.se/wp-json/wp/v2/posts |
| swiss_government_excellence_scholarships | sbfi.admin.ch | html | html/200 | - | - | true | JS-rendered:nuxt |
| swiss_national_science_foundation_snsf | snf.ch | needs_manual_review | error/- | - | - | true | api:gave up after 3 attempts: network error: [Errno 11001] getad |
| turkiye_scholarships | turkiyeburslari.gov.tr | blocked_document | html/200 | - | - | false | 403 |
| uk_research_and_innovation_ukri | ukri.org | rss | error/- | - | rss | true | api:client error (url=https://www.ukri.org/wp-json/wp/v2/opportu |
| un_careers_internship_programme | careers.un.org | html | html/200 | - | - | true |  |
| university_of_melbourne | scholarships.unimelb.edu.au | html | html/200 | - | - | true |  |
| university_of_oxford_graduate_funding | ox.ac.uk | html | error/- | - | - | true | api:client error (url=https://www.ox.ac.uk/api/v1/funding-opport |
| university_of_tokyo | u-tokyo.ac.jp | needs_manual_review | error/- | - | - | true | api:client error (url=https://www.u-tokyo.ac.jp/api/search.json, |
| vanier_canada_graduate_scholarships | vanier.gc.ca | needs_manual_review | error/- | - | - | true | api:gave up after 3 attempts: network error: [SSL: CERTIFICATE_V |
| visegrad_fund | visegradfund.org | html | html/200 | - | - | true |  |
| wellcome_sanger_institute | sanger.ac.uk | needs_manual_review | error/- | - | - | true | api:client error (url=https://www.sanger.ac.uk/wp-json/wp/v2/pos |
| wikicfp | wikicfp.com | rss | html/200 | - | rss | true |  |
| woods_hole_oceanographic_institution_whoi | whoi.edu | blocked_document | wp_rest/200 | yes | - | true | 403 |
| world_academy_of_sciences_twas_unesco | twas.org | html | error/- | - | - | true | api:client error (url=https://twas.org/wp-json/wp/v2/posts, stat |
| yale_university_macmillan_center | macmillan.yale.edu | html | html/200 | - | - | true |  |
| youth_opportunities | youthop.com | wp_rest | wp_rest/200 | yes | - | true |  |

## Raw source scope frequency (taxonomy discovery input)

- phd: 47
- postdoc: 36
- fellowships: 34
- scholarships: 31
- masters: 17
- exchange_programs: 12
- grants: 11
- workshops: 11
- conferences: 9
- internships: 7
- research_grants: 7
- summer_schools: 4
- visiting_fellowships: 4
- postdocs: 4
- symposia: 4
- competitions: 3
- phd_studentships: 3
- doctoral_grants: 2
- awards: 2
- postdoc_grants: 2
- physics_fellowships: 2
- phd_fellowships: 2
- phd_grants: 2
- travel_grants: 2
- phd_schools: 2
- doctoral_programs: 1
- technical_studentships: 1
- phd_research: 1
- research_student: 1
- research: 1
- doctoral_fellowships: 1
- group_leads: 1
- research_positions: 1
- phd_sandwich: 1
- spdr_postdoc: 1
- data_science_fellowships: 1
- phd_enrichment: 1
- summer_fellowships: 1
- graduate_fellowships: 1
- postgraduate: 1
- humanities_fellowships: 1
- visiting_research: 1
- call_for_papers: 1
- faculty_jobs: 1
- academic_jobs: 1
- faculty: 1
- research_mobility: 1
- travel_awards: 1
- doctoral_exchanges: 1
- seminar_awards: 1
- summer_universities: 1
- research_projects: 1
- graduate: 1
- bursaries: 1
- postdoc_fellowships: 1
- sabbatical_fellowships: 1
- doctoral_awards: 1
- studentships: 1
- summer_program: 1
- computational_fellowships: 1
- visiting_scholar: 1
