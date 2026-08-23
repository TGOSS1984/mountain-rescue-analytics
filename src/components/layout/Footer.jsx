import logo from "../../assets/brand/logo.svg";
import "./Footer.css";

/**
 * Attribution matters here beyond just looking professional — OSM's
 * and Nominatim's usage policies genuinely expect visible credit when
 * their data or geocoding is used, and each mountain rescue team's
 * incident log is their own published record, not "public data" in
 * the sense of being free of any expectation of acknowledgement.
 */
export default function Footer({ stats }) {
  const year = new Date().getFullYear();

  return (
    <footer className="site-footer">
      <div className="container site-footer__inner">
        <div className="site-footer__brand">
          <img src={logo} alt="" className="site-footer__mark" width="28" height="28" />
          <div>
            <p className="site-footer__brand-name">Mountain Rescue Analytics</p>
            <p className="site-footer__tagline">
              A portfolio project by{" "}
              <a href="https://github.com/TGOSS1984" target="_blank" rel="noreferrer">
                Tom Goss
              </a>
            </p>
            {stats?.date_range_start && stats?.date_range_end && (
              <p className="site-footer__coverage">
                Incident data covers {stats.date_range_start} to {stats.date_range_end}
              </p>
            )}
          </div>
        </div>

        <div className="site-footer__col">
          <p className="site-footer__heading">Incident data</p>
          <ul className="site-footer__links">
            <li>
              <a href="https://edalemrt.co.uk/incident/" target="_blank" rel="noreferrer">
                Edale Mountain Rescue Team
              </a>
            </li>
            <li>
              <a href="https://www.wmrt.org.uk/report-page/" target="_blank" rel="noreferrer">
                Wasdale Mountain Rescue Team
              </a>
            </li>
            <li>
              <a href="https://ogwen-rescue.org.uk/incident-details/" target="_blank" rel="noreferrer">
                Ogwen Valley Mountain Rescue Organisation
              </a>
            </li>
          </ul>
        </div>

        <div className="site-footer__col">
          <p className="site-footer__heading">Mapping &amp; weather</p>
          <ul className="site-footer__links">
            <li>
              <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
                © OpenStreetMap contributors
              </a>
            </li>
            <li>
              <a href="https://nominatim.org/" target="_blank" rel="noreferrer">
                Geocoding via Nominatim
              </a>
            </li>
            <li>
              <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">
                Weather via Open-Meteo
              </a>
            </li>
          </ul>
        </div>

        <div className="site-footer__col">
          <p className="site-footer__heading">Project</p>
          <ul className="site-footer__links">
            <li>
              <a
                href="https://github.com/TGOSS1984/mountain-rescue-analytics"
                target="_blank"
                rel="noreferrer"
              >
                Source on GitHub
              </a>
            </li>
            <li>
              <a
                href="https://github.com/TGOSS1984/mountain-rescue-analytics/blob/main/docs/data-dictionary.md"
                target="_blank"
                rel="noreferrer"
              >
                Data dictionary &amp; methodology
              </a>
            </li>
          </ul>
        </div>
      </div>

      <div className="container site-footer__bottom">
        <p>
          © {year} Tom Goss. Built with real, public incident data — not affiliated with
          any mountain rescue organisation.
        </p>
      </div>
    </footer>
  );
}