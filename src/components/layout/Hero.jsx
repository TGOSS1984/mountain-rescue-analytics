import heroImage from "../../assets/hero/hero-background.jpg";
import "./Hero.css";

/**
 * Hero stats are driven by the real /stats response, not hardcoded —
 * this is a live dashboard reflecting whatever the pipeline last
 * produced, not a mockup with placeholder numbers baked in.
 *
 * Background is a real photo (src/assets/hero/hero-background.jpg),
 * layered under a blurred, gradient scrim: solid enough on the left
 * for the text to stay readable, progressively clearer toward the
 * right so the photo actually shows through rather than being hidden
 * entirely. See Hero.css for the actual layering.
 */
export default function Hero({ stats, loading, error }) {
  return (
    <section className="hero">
      <div className="hero__bg" style={{ backgroundImage: `url(${heroImage})` }} aria-hidden="true" />
      <div className="hero__scrim" aria-hidden="true" />
      <div className="container hero__content">
        <p className="eyebrow hero__eyebrow">Real callout data, three regions</p>
        <h1 className="hero__title">
          Real callouts. Real weather.
          <br />
          Real terrain.
        </h1>
        <p className="hero__lead">
          Every incident logged by mountain rescue teams in the Peak District, Lake
          District, and Snowdonia, cleaned, geocoded, and laid out so you can see the
          real pattern behind them.
        </p>

        {error && (
          <p className="hero__error" role="alert">
            Couldn't reach the API — is it running? ({error})
          </p>
        )}

        {!error && (
          <dl className="hero__stats">
            <div className="hero__stat">
              <dt className="visually-hidden">Total incidents</dt>
              <dd className="hero__stat-num">
                {loading ? "…" : stats?.total_incidents?.toLocaleString() ?? "—"}
              </dd>
              <dt className="hero__stat-label">Total incidents</dt>
            </div>
            <div className="hero__stat">
              <dt className="visually-hidden">Regions covered</dt>
              <dd className="hero__stat-num">
                {loading ? "…" : stats?.regions?.length ?? "—"}
              </dd>
              <dt className="hero__stat-label">Regions covered</dt>
            </div>
            <div className="hero__stat">
              <dt className="visually-hidden">Geocoded match rate</dt>
              <dd className="hero__stat-num">
                {loading
                  ? "…"
                  : stats
                  ? `${Math.round(stats.geocode_match_rate * 100)}%`
                  : "—"}
              </dd>
              <dt className="hero__stat-label">Mapped to a location</dt>
            </div>
          </dl>
        )}
      </div>
    </section>
  );
}