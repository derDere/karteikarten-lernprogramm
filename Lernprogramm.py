""" Dieses Programm ist ein Karteikarten-Lernprogramm. Es stellt einen HTTP-Server bereit, der Karteikarten anzeigt.
    Jede Karteikarten-Gruppe wird als einzelne TXT-Datei im lokalen Verzeichnis gespeichert.
    Die Karteikarten werden in dieser Datei furch das Word "NEW" getrennt.
    Die einzelnen Seiten einer Karteikarte werden durch das Wort "FLIP" getrennt.
    Der Server stellt im root Verzeichnis eine Liste aller Karteikarten-Gruppen bereit.
    Nach dem Öffnen einer Karteikarten-Gruppe wird die Lernseite angezeigt auf der man die Karteikarten von
    Links nach Rechts durchgehen kann, wobei eine einzelne immer Mittig dargestellt wird.
    Mitting unten gibt es drei Buttons: "Flip", "Skip" und "Done".
    "Flip" dreht die Karteikarte um und zeigt die Rückseite.
    "Skip" überspringt die aktuelle Karteikarte und zeigt die nächste an.
    Übersprungne Karteikarten bleiben auf der Linken seite und können später nochmal bearbeitet werden.
    "Done" stellt eine Kartekarte als gelernt dar und zeigt die nächste an.
    Gelernte Karteikarten werden auf der Rechten Seite angezeigt und können später nochmal bearbeitet werden.
    Zudem gibt es einen Home Link oben mittig, der einen zurück zur Karteikarten-Gruppen-Liste bringt.
"""


from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import re
import markdown
import random
from urllib.parse import urlparse


CSS = """
  html, body {
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 0;
    height: 100%;
    min-height: 100%;
    overflow: auto;
  }

  .home {
    margin: 20px;
    display: inline-block;
    min-width: 200px;
    box-shadow: 0 0 15px rgba(0,0,0,0.5);
    padding: 20px;
    background: #ff7;
  }

  .home li {
    text-align: left;
  }

  a {
    color: #07f;
    text-decoration: none;
  }

  table.anzeige-tabelle td {
    vertical-align: top;
  }

  .links, .rechts {
    width: 440px;
    height: 100%;
    overflow: auto;
    display: inline-block;
    vertical-align: top;
  }

  .mitte {
    width: 440px;
    height: 100%;
    display: inline-block;
    vertical-align: top;
  }

  .anzeige {
    height: 270px;
  }

  h2 {
    text-align: center;
  }

  .buttons {
    text-align: center;
  }

  .karte {
    box-shadow: 0 0 15px rgba(0,0,0,0.5);
    width: 400px;
    height: 250px;
    box-sizing: border-box;
    color: #307;
    font-family: Courier New, monospace;
    padding: 10px;
  }

  .links, .rechts, .mitte .anzeige {
    padding: 20px;
  }

  .links .karte, .rechts .karte {
    background-color: #ff7;
    height: 20px;
  }

  .links .karte .f,
  .links .karte .b,
  .rechts .karte .f,
  .rechts .karte .b {
    display: none;
  }

  .links .karte:last-child,
  .rechts .karte:last-child {
    height: 250px;
  }

  .links .karte:last-child .f,
  .rechts .karte:last-child .b {
    display: block;
    filter: blur(3px);
  }

  .mitte .anzeige .karte {
    background-color: #ff7;
  }

  .mitte .anzeige.flipped .karte {
    background-color: #f7f;
  }

  .mitte .anzeige .karte .b {
    display: none;
  }

  .mitte .anzeige.flipped .karte .f {
    display: none;
  }

  .mitte .anzeige.flipped .karte .b {
    display: block;
  }

  .rechts .karte {
    background-color: #7f7;
  }

  .home-lnk {
    margin: 20px;
    display: block;
  }
"""


SCRIPT = """
  function MoveLeftToMiddle() {
    var lastCardLeftSide = document.querySelector(".links .karte:last-child");
    if (!lastCardLeftSide) return;
    var middle = document.querySelector(".mitte .anzeige");
    middle.appendChild(lastCardLeftSide);
  }

  function Flip() {
    var middle = document.querySelector(".mitte .anzeige");
    middle.classList.toggle("flipped");
  }

  function Skip() {
    var middle = document.querySelector(".mitte .anzeige");
    middle.classList.remove("flipped");

    var card = document.querySelector(".mitte .anzeige .karte");
    if (!card) return;

    var left = document.querySelector(".links");
    left.insertBefore(card, left.firstChild);

    MoveLeftToMiddle();
  }

  function Done() {
    var middle = document.querySelector(".mitte .anzeige");
    middle.classList.remove("flipped");

    var card = document.querySelector(".mitte .anzeige .karte");
    if (!card) return;

    var right = document.querySelector(".rechts");
    right.appendChild(card);

    MoveLeftToMiddle();
  }

  MoveLeftToMiddle();
"""


def CamelCaseToDisplayName(name:str) -> str:
  """Wandelt einen CamelCase-String in einen Anzeige-String um.
  """
  name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
  name = re.sub(r"\s{2,}", r" ", name)
  name = name.strip()
  return name


def _ClearLine(line:str) -> str:
  """Entfernt unnötige Zeichen aus einer Zeile.
  """
  return line.replace("-","").replace("=","").replace("#","").replace("_","").strip()


def LineIsNew(line:str) -> bool:
  """Überprüft, ob eine Zeile eine neue Karteikarte anzeigt.
  """
  return _ClearLine(line).upper() == "NEW"


def LineIsFlip(line:str) -> bool:
  """Überprüft, ob eine Zeile eine neue Karteikarte anzeigt.
  """
  return _ClearLine(line).upper() == "FLIP"


class Karteikarte:
  """Klasse für eine einzelne Karteikarte.
  """

  front:str
  back:str

  def __init__(self, front:str, back:str) -> None:
    self.front = front
    self.back = back

  def to_html(self) -> str:
    """Gibt die Karteikarte als HTML-String zurück.
    """
    return f"""
      <div class="karte">
        <div class="f">{markdown.markdown(self.front, extensions=["tables", "fenced_code"])}</div>
        <div class="b">{markdown.markdown(self.back, extensions=["tables", "fenced_code"])}</div>
      </div>
    """


class KarteikartenGruppe:
  """Klasse für eine Gruppe von Karteikarten.
  """

  name:str
  karteikarten:list[Karteikarte]

  def __init__(self) -> None:
    self.name = "???"
    self.id = "???"
    self.karteikarten = []

  def read_from_file(self, filename:str) -> None:
    """Liest die Karteikarten-Gruppe aus einer Datei.
    """
    with open(filename, "r", encoding="utf-8") as file:
      self.name = CamelCaseToDisplayName(os.path.basename(filename).split(".")[0])
      self.id = os.path.basename(filename).split(".")[0]
      front_lines:list[str] = []
      back_lines:list[str] = []
      current_lines:list[str] = []
      # for each line if file
      for line in file:
        # if line is "NEW" then create a new Karteikarte
        if LineIsNew(line):
          back_lines = current_lines
          current_lines = []
          if len(front_lines) > 0 or len(back_lines) > 0:
            self.karteikarten.append(Karteikarte("\n".join(front_lines), "\n".join(back_lines)))
          front_lines = []
          back_lines = []
        # if line is "FLIP" then switch to back side
        elif LineIsFlip(line):
          front_lines = current_lines
          current_lines = []
        # else add line to current side
        elif len(line.strip()) > 0:
          if line.strip() == ".":
            current_lines.append("")
          else:
            current_lines.append(line.strip())
      back_lines = current_lines
      current_lines = []
      if len(front_lines) > 0 or len(back_lines) > 0:
        self.karteikarten.append(Karteikarte("\n".join(front_lines), "\n".join(back_lines)))

  def to_html(self) -> str:
    """Gibt die Karteikarten-Gruppe als HTML-String zurück.
    """
    random.shuffle(self.karteikarten)
    return "".join([k.to_html() for k in self.karteikarten])

  def to_list_item(self) -> str:
    """Gibt die Karteikarten-Gruppe als HTML-Listenelement zurück.
    """
    return f"""
      <li><a href="/{self.id}">{self.name}</a></li>
    """


class HomePage:
  """Klasse für die Startseite des Servers.
  """

  gruppen:list[KarteikartenGruppe]

  def __init__(self) -> None:
    self.gruppen = []

  def read_from_directory(self, directory:str) -> None:
    """Liest die Karteikarten-Gruppen aus einem Verzeichnis.
    """
    for filename in os.listdir(directory):
      if filename.endswith(".txt"):
        gruppe = KarteikartenGruppe()
        gruppe.read_from_file(os.path.join(directory, filename))
        self.gruppen.append(gruppe)

  def to_html(self) -> str:
    """Gibt die Startseite als HTML-String zurück.
    """
    return f"""
      <div class="home">
        <ul>
          {"".join([g.to_list_item() for g in self.gruppen])}
        </ul>
      </div>
    """


class KarteikartenServerBase(HTTPServer):
  """Klasse für den HTTP-Server.
  """
  homepage:HomePage


class KarteikartenServerHandler(BaseHTTPRequestHandler):
  """Klasse für den HTTP-Server.
  """

  server:KarteikartenServerBase # type: ignore

  def do_GET(self) -> None:
    """Verarbeitet eine HTTP-GET-Anfrage.
    """
    # parse the URL
    url = urlparse(self.path)
    # if the URL is the root URL
    if url.path == "/":
      # send the home page
      self.send_response(200)
      self.send_header("Content-type", "text/html")
      self.end_headers()
      self.wfile.write(f"""
        <html>
          <head>
            <title>Karteikarten</title>
            <style>{CSS}</style>
            <meta charset="utf-8">
          </head>
          <body>
            <center>
            <h1>Karteikarten</h1>
            {self.server.homepage.to_html()}
            </center>
            <script type="text/javascript">{SCRIPT}</script>
          </body>
        </html>
      """.encode("utf-8"))
    # if the URL is a group URL
    elif url.path[1:] in [g.id for g in self.server.homepage.gruppen]:
      # send the group page
      gruppe = [g for g in self.server.homepage.gruppen if g.id == url.path[1:]][0]
      self.send_response(200)
      self.send_header("Content-type", "text/html")
      self.end_headers()
      self.wfile.write(f"""
        <html>
          <head>
            <title>{gruppe.name}</title>
            <style>{CSS}</style>
            <meta charset="utf-8">
          </head>
          <body>
            <a class="home-lnk" href="/">Home</a>
            <center>
            <h1>{gruppe.name}</h1>
            <table class="anzeige-tabelle">
              <tr>
                <td>
                  <h2>Zu Lernen</h2>
                  <div class="links">
                    {gruppe.to_html()}
                  </div>
                </td>
                <td>
                  <div class="mitte">
                    <h2>&#160;</h2>
                    <div class="anzeige">
                    </div>
                    <div class="buttons">
                      <button onclick="Flip();">Flip</button>
                      <button onclick="Skip();">Skip</button>
                      <button onclick="Done();">Done</button>
                    </div>
                  </div>
                </td>
                <td>
                  <h2>Gelernt</h2>
                  <div class="rechts">
                  </div>
                </td>
              </tr>
            </table>
            </center>
            <script type="text/javascript">{SCRIPT}</script>
          </body>
        </html>
      """.encode("utf-8"))
    # if the URL is unknown
    else:
      # send a 404 error
      self.send_response(404)
      self.send_header("Content-type", "text/html")
      self.end_headers()
      self.wfile.write(f"""
        <html>
          <head>
            <title>404 Not Found</title>
            <style>{CSS}</style>
            <meta charset="utf-8">
          </head>
          <body>
            <h1>404 Not Found</h1>
            <p>The requested URL {url.path} was not found on this server.</p>
          </body>
        </html>
      """.encode("utf-8"))


class KarteikartenServer(KarteikartenServerBase):
  """Klasse für den HTTP-Server.
  """

  def __init__(self, homepage:HomePage, server_address:tuple[str, int], handler_class:type[KarteikartenServerHandler]) -> None:
    super().__init__(server_address, handler_class)
    self.homepage = homepage


def main() -> None:
  """Hauptfunktion des Programms.
  """
  # create the home page
  homepage = HomePage()
  homepage.read_from_directory(".")
  # create the server
  server = KarteikartenServer(homepage, ("", 8000), KarteikartenServerHandler)
  # open web browser
  os.system("start http://localhost:8000")
  # run the server
  server.serve_forever()


if __name__ == "__main__":
  main()
