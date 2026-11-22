import { type MouseEvent, useEffect, useState } from 'react';
import { CircleAlert, RotateCw } from 'lucide-react';
import { type DatasetSummary, getDatasetSummary, getPollenCalendar, type PollenCalendar } from './api';

const MONTHS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
const SHORT = ['Janv.', 'Févr.', 'Mars', 'Avr.', 'Mai', 'Juin', 'Juil.', 'Août', 'Sept.', 'Oct.', 'Nov.', 'Déc.'];
const INITIAL = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];

const integer = new Intl.NumberFormat('fr-FR');
const decimal = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 });

interface Tip { x: number; y: number; text: string }

/** One hover tooltip shared by every chart on the page. */
function useTooltip() {
  const [tip, setTip] = useState<Tip | null>(null);
  const show = (event: MouseEvent, text: string) => setTip({ x: event.clientX, y: event.clientY, text });
  const hide = () => setTip(null);
  const node = tip && (
    <div className="tooltip" style={{ left: tip.x, top: tip.y }} role="presentation">{tip.text}</div>
  );
  return { show, hide, node };
}

function peakMonth(values: number[]): number {
  return values.indexOf(Math.max(...values));
}

export default function DataPage() {
  const [summary, setSummary] = useState<DatasetSummary | null>(null);
  const [pollens, setPollens] = useState<PollenCalendar | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const tooltip = useTooltip();

  useEffect(() => {
    let active = true;
    setError(null);
    Promise.all([getDatasetSummary(), getPollenCalendar()])
      .then(([data, calendar]) => { if (active) { setSummary(data); setPollens(calendar); } })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Impossible de charger les statistiques.');
      });
    return () => { active = false; };
  }, [reload]);

  if (error) {
    return (
      <div className="page">
        <div className="notice notice--error" role="alert">
          <CircleAlert size={18} aria-hidden="true" />
          <span>{error}</span>
          <button className="ghost" onClick={() => setReload((value) => value + 1)}><RotateCw size={14} aria-hidden="true" /> Réessayer</button>
        </div>
      </div>
    );
  }

  if (!summary || !pollens) {
    return <div className="page"><div className="notice" role="status"><span className="spinner" /> Chargement des statistiques…</div></div>;
  }

  const maxMonth = Math.max(...summary.sampling_months);
  const busiestMonth = summary.sampling_months.indexOf(maxMonth);
  const taxa = [...pollens.taxa].sort((a, b) => peakMonth(a.monthly_mean) - peakMonth(b.monthly_mean) || a.taxon.localeCompare(b.taxon, 'fr'));
  const leastFilled = [...summary.fields].sort((a, b) => b.missing - a.missing).slice(0, 10);

  return (
    <div className="page" onMouseLeave={tooltip.hide}>
      <header className="page__head">
        <h1>Données</h1>
        <p>Statistiques agrégées, calculées en Python sur votre machine. Le navigateur ne reçoit aucune ligne de patient.</p>
      </header>

      <section className="tiles" aria-label="Chiffres clés">
        <div className="tile"><span className="tile__label">Patients</span><strong>{integer.format(summary.rows)}</strong></div>
        <div className="tile">
          <span className="tile__label">Colonnes</span><strong>{summary.columns}</strong>
          <span className="tile__note">{summary.clinical_columns} cliniques, {summary.dosage_columns} dosages</span>
        </div>
        <div className="tile">
          <span className="tile__label">Puces</span><strong>{Object.keys(summary.chips).length}</strong>
          <span className="tile__note">{Object.entries(summary.chips).map(([chip, n]) => `${chip} ${integer.format(n)}`).join(' · ')}</span>
        </div>
        <div className="tile">
          <span className="tile__label">Cellules renseignées</span><strong>{decimal.format(summary.completeness_percent)} %</strong>
          <span className="tile__note">un dosage vide : non mesuré par la puce</span>
        </div>
      </section>

      <section className="card">
        <header className="card__head">
          <div>
            <h2>Prélèvements et pollens, mois par mois</h2>
            <p>
              En haut, le nombre de patients prélevés chaque mois (le tableau ne donne pas l'année).
              En dessous, la saison de chaque pollen dans l'air de France métropolitaine. Le mois est le seul lien entre les deux.
            </p>
          </div>
        </header>

        <div className="months" role="img" aria-label={`Patients prélevés par mois, au plus ${integer.format(maxMonth)} en ${MONTHS[busiestMonth]}`}>
          <span className="months__axis">Patients</span>
          {summary.sampling_months.map((count, index) => (
            <div
              key={index}
              className="months__col"
              onMouseMove={(event) => tooltip.show(event, `${MONTHS[index]} : ${integer.format(count)} patients prélevés`)}
              onMouseLeave={tooltip.hide}
            >
              {index === busiestMonth && <span className="months__label">{integer.format(count)}</span>}
              <span className="months__bar" style={{ height: `${(100 * count) / maxMonth}%` }} />
            </div>
          ))}
        </div>

        <div className="heatmap" role="table" aria-label="Calendrier pollinique moyen de la France métropolitaine">
          <div className="heatmap__row heatmap__row--head" role="row">
            <span role="columnheader" className="heatmap__name">
              <span className="long">Pollen ou moisissure</span><span className="short">Taxon</span>
            </span>
            {SHORT.map((month, index) => (
              <span role="columnheader" key={month} className="heatmap__month">
                <span className="long">{month}</span><span className="short" aria-hidden="true">{INITIAL[index]}</span>
              </span>
            ))}
          </div>
          {taxa.map((taxon) => {
            const peak = Math.max(...taxon.monthly_mean);
            return (
              <div className="heatmap__row" role="row" key={taxon.taxon}>
                <span role="rowheader" className="heatmap__name" title={`${taxon.taxon} · colonnes du tableau : ${taxon.acc_allergens}`}>
                  <span>{taxon.taxon}</span><small>{taxon.acc_allergens.split(' ')[0]}</small>
                </span>
                {taxon.monthly_mean.map((value, index) => {
                  const share = peak > 0 ? value / peak : 0;
                  const label = `${taxon.taxon}, ${MONTHS[index]} : ${decimal.format(value)} grains/m³ par jour en moyenne${index === peakMonth(taxon.monthly_mean) ? ' (pic)' : ''}`;
                  return (
                    <span
                      role="cell"
                      key={index}
                      aria-label={label}
                      className={`heatmap__cell ${share < 0.02 ? 'heatmap__cell--empty' : ''}`}
                      style={share >= 0.02 ? { background: `color-mix(in oklab, var(--viz-seq) ${Math.round(12 + 88 * share)}%, var(--viz-floor))` } : undefined}
                      onMouseMove={(event) => tooltip.show(event, label)}
                      onMouseLeave={tooltip.hide}
                    />
                  );
                })}
              </div>
            );
          })}
        </div>

        <footer className="card__foot">
          <span className="legend">
            <span className="legend__ramp" aria-hidden="true" />
            <span>Chaque ligne est rapportée à son propre pic : foncé = mois le plus chargé de ce taxon.</span>
          </span>
          <span className="source">Source : {pollens.source}.</span>
        </footer>

        <details className="table-view">
          <summary>Voir les valeurs en tableau</summary>
          <div className="table-scroll">
            <table>
              <thead>
                <tr><th scope="col">Taxon</th>{SHORT.map((month) => <th scope="col" key={month}>{month}</th>)}</tr>
              </thead>
              <tbody>
                <tr><th scope="row">Patients prélevés</th>{summary.sampling_months.map((n, i) => <td key={i}>{integer.format(n)}</td>)}</tr>
                {taxa.map((taxon) => (
                  <tr key={taxon.taxon}>
                    <th scope="row">{taxon.taxon}</th>
                    {taxon.monthly_mean.map((value, i) => <td key={i}>{decimal.format(value)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="source">Pollens : moyenne journalière en grains/m³ d'air. {integer.format(summary.sampling_month_missing)} patients n'ont pas de mois de prélèvement.</p>
        </details>
      </section>

      <section className="card">
        <header className="card__head">
          <div>
            <h2>Colonnes les moins renseignées</h2>
            <p>Cases vides sur {integer.format(summary.rows)} patients. Pour un dosage, une case vide veut souvent dire que la puce du patient ne le mesure pas.</p>
          </div>
        </header>
        <ul className="bars">
          {leastFilled.map((field) => (
            <li
              key={field.name}
              onMouseMove={(event) => tooltip.show(event, `${field.name} : ${integer.format(field.missing)} cases vides, ${decimal.format(field.completeness_percent)} % renseignées`)}
              onMouseLeave={tooltip.hide}
            >
              <span className="bars__name">{field.name}</span>
              <span className="bars__track"><span className="bars__fill" style={{ width: `${(100 * field.missing) / summary.rows}%` }} /></span>
              <span className="bars__value">{integer.format(field.missing)}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <header className="card__head"><div><h2>Sources</h2></div></header>
        <ul className="sources">
          <li>
            <a href="https://doi.org/10.60597/j5fe-g420" target="_blank" rel="noreferrer">Allergen Chip Challenge</a>
            <span>Société Française d'Allergologie · Licence Ouverte 2.0 · le tableau des patients, dans <code>donnees/</code></span>
          </li>
          <li>
            <a href="https://www.data.gouv.fr/datasets/donnees-historiques-de-surveillance-des-pollens-et-des-moisissures" target="_blank" rel="noreferrer">Surveillance des pollens et des moisissures</a>
            <span>RNSA, Ministère chargé de la santé · Licence Ouverte 2.0 · dans <code>donnees_complementaires/</code></span>
          </li>
          <li>
            <a href="https://www.data.gouv.fr/datasets/risque-allergique-lie-aux-pollens-de-la-metropole-de-lyon-historique" target="_blank" rel="noreferrer">Risque allergique lié aux pollens, Lyon</a>
            <span>Métropole de Lyon · Licence Ouverte 2.0 · dans <code>donnees_complementaires/</code></span>
          </li>
        </ul>
      </section>

      {tooltip.node}
    </div>
  );
}
