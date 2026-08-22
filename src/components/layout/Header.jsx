import logo from "../../assets/brand/logo.svg";
import "./Header.css";

export default function Header() {
  return (
    <header className="site-header">
      <div className="container site-header__inner">
        <div className="brand">
          <img src={logo} alt="" className="brand__mark" width="32" height="32" />
          <span className="brand__name">Mountain Rescue Analytics</span>
        </div>
        <nav aria-label="Primary" className="site-nav">
          <a href="#overview" className="site-nav__link is-active">
            Overview
          </a>
          <a href="#incidents" className="site-nav__link">
            Incidents
          </a>
          <a href="#regions" className="site-nav__link">
            Regions
          </a>
          <a
            href="https://github.com/TGOSS1984/mountain-rescue-analytics"
            className="site-nav__link"
            target="_blank"
            rel="noreferrer"
          >
            Methodology
          </a>
        </nav>
      </div>
    </header>
  );
}