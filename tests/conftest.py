import pytest


@pytest.fixture
def sample_cnbv_rss() -> str:
    """Minimal DOF RSS feed with one CNBV-relevant entry."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>DOF - Diario Oficial de la Federación</title>
    <item>
      <title>Circular CNBV 5/2025 - Límites de apalancamiento para SOFOMs</title>
      <link>https://www.dof.gob.mx/nota_detalle.php?codigo=5756789&amp;fecha=20/03/2025</link>
      <description>Se reducen los límites de contraparte del 20% al 15%.</description>
      <pubDate>Thu, 20 Mar 2025 00:00:00 +0000</pubDate>
      <guid>https://www.dof.gob.mx/nota_detalle.php?codigo=5756789</guid>
    </item>
    <item>
      <title>Decreto presidencial sobre política exterior</title>
      <link>https://www.dof.gob.mx/nota_detalle.php?codigo=9999999</link>
      <description>Contenido no relacionado con CNBV.</description>
      <pubDate>Thu, 20 Mar 2025 00:00:00 +0000</pubDate>
      <guid>https://www.dof.gob.mx/nota_detalle.php?codigo=9999999</guid>
    </item>
  </channel>
</rss>"""


@pytest.fixture
def sample_sec_rss() -> str:
    """Minimal SEC press release feed with one rule-related entry."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>SEC Press Releases</title>
    <item>
      <title>SEC Adopts Final Rule on Climate-Related Disclosures</title>
      <link>https://www.sec.gov/news/press-release/2025-001</link>
      <description>The Commission adopts final rule amending Regulation S-K.</description>
      <pubDate>Mon, 20 Jan 2025 12:00:00 GMT</pubDate>
      <guid>https://www.sec.gov/news/press-release/2025-001</guid>
    </item>
    <item>
      <title>SEC Charges Company with Fraud</title>
      <link>https://www.sec.gov/news/press-release/2025-002</link>
      <description>Enforcement action against XYZ Corp.</description>
      <pubDate>Tue, 21 Jan 2025 12:00:00 GMT</pubDate>
      <guid>https://www.sec.gov/news/press-release/2025-002</guid>
    </item>
  </channel>
</rss>"""
