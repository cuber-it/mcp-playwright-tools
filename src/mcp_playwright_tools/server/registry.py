"""The tools as a catalogue a server can publish.

:func:`catalogue` binds every tool to one shared workspace and returns them by
the name they are published under. It knows no server and imports no SDK:
whatever publishes the catalogue, the MCP SDK in :mod:`.app` or a server
library of our own, takes it from here.

``screenshot`` may return a :class:`~mcp_playwright_tools.read.Picture`; the
publisher turns it into what its protocol calls an image. **The docstring of a
wrapper is the description that lands in the client's catalogue.** Each has an
English part, a German paragraph, and a closing line of German search words.

Names carry no prefix. Putting one in front is the publisher's business.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from mcp_playwright_tools import act, examine, keep, navigate
from mcp_playwright_tools import read as reading
from mcp_playwright_tools.pool import DEFAULT_CONTEXT
from mcp_playwright_tools.read import Picture
from mcp_playwright_tools.workspace import Workspace

Tool = Callable[..., Awaitable[Any]]
Catalogue = dict[str, Tool]


def catalogue(space: Workspace) -> Catalogue:
    """Return every tool bound to the workspace, by its published name."""
    tools = [
        *_going(space),
        *_finding(space),
        *_doing(space),
        *_reading(space),
        *_keeping(space),
    ]
    return {tool.__name__: tool for tool in tools}


def _going(space: Workspace) -> list[Tool]:
    """Return the tools that move between pages, tabs and frames."""

    async def open_url(url: str, context: str = DEFAULT_CONTEXT) -> str:
        """Open a web page in the browser and wait until its document has loaded.

        Without a scheme, https is assumed; a file: address opens a page from
        disk. Returns the address the browser ended up at, which differs after
        a redirect. Every tool takes context, a name: each name is a browser
        context of its own with its own cookies, storage and tabs, closed when
        nobody has used it for a while.

        Öffnet eine Webseite im Browser und wartet, bis das Dokument geladen
        ist. Ohne Schema gilt https, eine file:-Adresse öffnet eine Seite von
        der Platte. Zurück kommt die Adresse nach einer Weiterleitung. context
        benennt einen eigenen Browser-Kontext mit eigenen Cookies, eigenem
        Speicher und eigenen Tabs; er wird geschlossen, wenn ihn eine Weile
        niemand nutzt.

        Stichworte: Webseite öffnen, aufrufen, URL laden, Seite besuchen.
        """
        return await navigate.open_url(space.browsing(context), url)

    async def go(direction: str = "back", context: str = DEFAULT_CONTEXT) -> str:
        """Go back or forward in the history, or load the page again.

        direction is back, forward or reload. Returns where the browser is
        afterwards.

        Geht im Verlauf zurück oder vor oder lädt die Seite neu; direction ist
        back, forward oder reload.

        Stichworte: zurück, vorwärts, neu laden, aktualisieren, Verlauf.
        """
        return await navigate.go(space.browsing(context), direction)

    async def where_am_i(context: str = DEFAULT_CONTEXT) -> dict[str, str]:
        """Report the address and the title of the page that is open.

        Cheap; use it to check where the browser stands before doing more.

        Nennt Adresse und Titel der offenen Seite. Günstig, um vor dem nächsten
        Schritt nachzusehen, wo der Browser steht.

        Stichworte: aktuelle Seite, welche URL, Adresse, Titel, wo bin ich.
        """
        return await navigate.where_am_i(space.browsing(context))

    async def tabs(
        action: str = "list", tab: int = -1, context: str = DEFAULT_CONTEXT
    ) -> str:
        """Work with tabs: list, open, switch or close.

        action is list, open, switch or close. switch and close need the tab's
        number in tab, which list reports. The tools act on the active tab.

        Arbeitet mit Tabs: auflisten, öffnen, wechseln, schließen. switch und
        close brauchen die Nummer des Tabs, die list nennt. Die Werkzeuge
        wirken auf den aktiven Tab.

        Stichworte: Tab öffnen, wechseln, schließen, Reiter, Registerkarte.
        """
        return await navigate.tabs(space.browsing(context), action, tab)

    async def use_frame(selector: str = "", context: str = DEFAULT_CONTEXT) -> str:
        """Work inside a frame, or go back to the page itself.

        Pass the frame's CSS selector to act inside it from now on; pass
        nothing to leave it.

        Arbeitet in einem Frame oder wieder in der Seite selbst. Mit dem
        CSS-Selektor des Frames wirken die folgenden Aufrufe darin, ohne
        Selektor wieder in der Seite.

        Stichworte: Frame wechseln, iframe, Rahmen, zurück zur Hauptseite.
        """
        return await navigate.use_frame(space.browsing(context), selector)

    return [open_url, go, where_am_i, tabs, use_frame]


def _finding(space: Workspace) -> list[Tool]:
    """Return the tools that look at what is on a page."""

    async def find(
        target: str, by: str = "css", name: str = "", context: str = DEFAULT_CONTEXT
    ) -> str:
        """Find elements on the page and list what was found.

        by says how target is meant: css (default), role, text, label,
        placeholder or testid. With by="role", name tells apart elements of the
        same role, for instance target button with name Save. Returns the
        count and up to twenty elements with tag and text.

        Findet Elemente auf der Seite und listet sie auf. by sagt, wie target
        gemeint ist: css, role, text, label, placeholder oder testid; bei role
        unterscheidet name gleichartige Elemente. Zurück kommen die Anzahl und
        bis zu zwanzig Elemente mit Tag und Text.

        Stichworte: Element finden, suchen, Knopf finden, Feld suchen, Link.
        """
        return await examine.find(space.browsing(context), target, by, name)

    async def describe(
        target: str, by: str = "css", context: str = DEFAULT_CONTEXT
    ) -> dict[str, Any]:
        """Describe one element: tag, text, attributes, visible, enabled.

        Use it before acting on something to see what it is and whether it can
        be used. by as in find.

        Beschreibt ein Element: Tag, Text, Attribute, ob es sichtbar und
        bedienbar ist. Vor einer Aktion nützlich, um zu sehen, was es ist.

        Stichworte: Element untersuchen, Attribute, sichtbar, anklickbar.
        """
        return await examine.describe(space.browsing(context), target, by)

    async def what_can_i_do(context: str = DEFAULT_CONTEXT) -> str:
        """List everything visible on the page that can be acted on.

        Buttons, links, inputs, selects and anything with a role, with id and
        role to find them again. The place to start on an unknown page.

        Listet alles Sichtbare auf, was sich bedienen lässt: Knöpfe, Links,
        Eingabefelder, Auswahllisten und Elemente mit Rolle, mit id und Rolle
        zum Wiederfinden. Der Einstieg auf einer unbekannten Seite.

        Stichworte: Bedienelemente, Knöpfe, Felder, Formular, was kann ich tun.
        """
        return await examine.what_can_i_do(space.browsing(context))

    async def outline(context: str = DEFAULT_CONTEXT) -> str:
        """Return the accessibility tree: headings, regions, controls, names.

        A structured view of what the page offers, usually more useful than the
        HTML for deciding what to do next.

        Gibt den Barrierefreiheitsbaum zurück: Überschriften, Bereiche,
        Bedienelemente und ihre Namen. Meist nützlicher als das HTML, um den
        nächsten Schritt zu wählen.

        Stichworte: Seitenstruktur, Gliederung, Überschriften, Aufbau.
        """
        return await examine.outline(space.browsing(context))

    return [find, describe, what_can_i_do, outline]


def _doing(space: Workspace) -> list[Tool]:
    """Return the tools that change something on a page."""

    async def click(
        target: str, by: str = "css", name: str = "", context: str = DEFAULT_CONTEXT
    ) -> str:
        """Click an element.

        by says how target is meant: css (default), role, text, label,
        placeholder or testid; with by="role", name picks by accessible name.
        Clicking by text or role survives a changed layout better than CSS.
        Playwright waits until the element can be clicked.

        Klickt ein Element an. by sagt, wie target gemeint ist; bei role wählt
        name nach dem zugänglichen Namen. Nach Text oder Rolle zu klicken hält
        Layoutänderungen besser aus als CSS.

        Stichworte: klicken, anklicken, Knopf drücken, Link folgen.
        """
        return await act.click(space.browsing(context), target, by, name)

    async def act_on(
        action: str, target: str, by: str = "css", context: str = DEFAULT_CONTEXT
    ) -> str:
        """Do something to an element other than a plain click.

        action is double_click, right_click, hover, focus, check, uncheck,
        clear or scroll_to. by as in click.

        Tut etwas anderes mit einem Element als einfach klicken: double_click,
        right_click, hover, focus, check, uncheck, clear oder scroll_to.

        Stichworte: doppelklicken, rechtsklicken, überfahren, Haken setzen,
        Feld leeren, hinscrollen.
        """
        return await act.act_on(space.browsing(context), action, target, by)

    async def fill(
        target: str,
        value: str,
        by: str = "label",
        typed: bool = False,
        context: str = DEFAULT_CONTEXT,
    ) -> str:
        """Put text into an input field.

        The field is found by its form label by default; css, role, text,
        placeholder and testid work too. With typed=true the text is entered
        key by key, slower, for pages that only react to real keystrokes.

        Schreibt Text in ein Eingabefeld, das standardmäßig über sein
        Formular-Label gefunden wird. Mit typed=true wird Taste für Taste
        getippt, für Seiten, die nur auf echte Tastendrücke reagieren.

        Stichworte: Feld ausfüllen, Text eingeben, Formular, eintippen.
        """
        return await act.fill(space.browsing(context), target, value, by, typed)

    async def press_key(
        key: str, target: str = "", by: str = "css", context: str = DEFAULT_CONTEXT
    ) -> str:
        """Press a key, on one element or on the page as a whole.

        Keys are named as Playwright names them: Enter, Escape, Tab,
        ArrowDown, Control+A.

        Drückt eine Taste auf einem Element oder auf der ganzen Seite. Tasten
        heißen wie bei Playwright: Enter, Escape, Tab, ArrowDown, Control+A.

        Stichworte: Taste drücken, Eingabetaste, Escape, Tastenkombination.
        """
        return await act.press_key(space.browsing(context), key, target, by)

    async def choose(
        target: str,
        option: str,
        by: str = "label",
        text: bool = False,
        context: str = DEFAULT_CONTEXT,
    ) -> str:
        """Choose an option in a dropdown.

        The option is matched by its value, with text=true by its visible
        text. The dropdown is found by its label by default.

        Wählt eine Option in einer Auswahlliste, nach ihrem Wert oder mit
        text=true nach dem sichtbaren Text. Die Liste wird standardmäßig über
        ihr Label gefunden.

        Stichworte: Auswahl treffen, Dropdown, Option wählen, Select-Feld.
        """
        return await act.choose(space.browsing(context), target, option, by, text)

    async def drag(
        source: str, destination: str, by: str = "css", context: str = DEFAULT_CONTEXT
    ) -> str:
        """Drag one element onto another.

        Both are found the same way, by as in click.

        Zieht ein Element auf ein anderes; beide werden auf dieselbe Weise
        gefunden.

        Stichworte: ziehen, verschieben, Drag and Drop.
        """
        return await act.drag(space.browsing(context), source, destination, by)

    async def scroll(amount: str = "down", context: str = DEFAULT_CONTEXT) -> str:
        """Scroll the page down, up, to the top or to the bottom.

        amount is down, up, top or bottom. To bring one element into view use
        act_on with scroll_to.

        Scrollt die Seite: down, up, top oder bottom. Ein einzelnes Element
        holt act_on mit scroll_to ins Bild.

        Stichworte: scrollen, blättern, nach unten, Seitenende, Seitenanfang.
        """
        return await act.scroll(space.browsing(context), amount)

    async def attach_files(
        target: str, paths: str, by: str = "css", context: str = DEFAULT_CONTEXT
    ) -> str:
        """Put files from this machine into a file input, as a user would.

        paths holds one path or several separated by commas; relative ones
        start in the server's working directory. The files have to lie where
        the server may read.

        Legt Dateien von diesem Rechner in ein Datei-Eingabefeld, wie beim
        Hochladen. Mehrere Pfade werden durch Kommas getrennt; relative gelten
        ab dem Arbeitsverzeichnis des Servers.

        Stichworte: Datei hochladen, anhängen, Upload, Dateiauswahl.
        """
        return await act.attach_files(space.browsing(context), target, paths, by)

    async def run_javascript(script: str, context: str = DEFAULT_CONTEXT) -> Any:
        """Run JavaScript in the page and return what it gives back.

        The last resort when no other tool fits; it runs with the page's own
        rights, also in a logged-in session. Off unless the host allows it: a
        refusal names the grant a person runs on the host.

        Führt JavaScript in der Seite aus und gibt das Ergebnis zurück. Letzter
        Ausweg, wenn kein anderes Werkzeug passt; läuft mit den Rechten der
        Seite. Aus, solange der Host es nicht erlaubt; eine Ablehnung nennt die
        Freigabe, die ein Mensch auf dem Host ausführt.

        Stichworte: JavaScript ausführen, Skript, Konsole, im Browser ausführen.
        """
        return await act.run_javascript(space.browsing(context), script)

    return [
        click,
        act_on,
        fill,
        press_key,
        choose,
        drag,
        scroll,
        attach_files,
        run_javascript,
    ]


def _reading(space: Workspace) -> list[Tool]:
    """Return the tools that read a page, photograph it and wait on it."""

    async def read(
        target: str = "",
        what: str = "text",
        attribute: str = "",
        by: str = "css",
        context: str = DEFAULT_CONTEXT,
    ) -> str:
        """Read something off the page: text, markup, an attribute or the links.

        what is one of: text, the visible text of the page or of the element
        target names (the default); texts, the text of every match, one per
        line, for lists and tables; html, the markup instead; attribute, one
        attribute named in attribute, for instance href; links, every link as
        text and address. by as in find. Long output is cut at 20000
        characters and says so.

        Liest etwas von der Seite: text (sichtbarer Text der Seite oder eines
        Elements), texts (Text jedes Treffers, zeilenweise), html (Markup),
        attribute (ein Attribut, benannt in attribute) oder links (alle Links
        mit Adresse).

        Stichworte: Seitentext lesen, auslesen, Tabelle, HTML, Attribut, Links.
        """
        return await reading.read(space.browsing(context), target, what, attribute, by)

    async def screenshot(
        target: str = "",
        by: str = "css",
        full: bool = False,
        save_to: str = "",
        context: str = DEFAULT_CONTEXT,
    ) -> Picture | str:
        """Take a screenshot and show it as a picture.

        Without target the visible part of the page is taken, with full=true
        the whole page; name an element to take only that. With save_to the
        picture is written to that file instead and the path comes back;
        writing has to be allowed there.

        Macht ein Bildschirmfoto und zeigt es als Bild: den sichtbaren Teil,
        mit full=true die ganze Seite oder nur ein Element. Mit save_to wird es
        stattdessen in diese Datei geschrieben.

        Stichworte: Bildschirmfoto, Screenshot, Seite fotografieren, Bild.
        """
        return await reading.screenshot(
            space.browsing(context), target, by, full, save_to
        )

    async def wait_until(
        what: str,
        value: str = "",
        by: str = "css",
        seconds: float = 30.0,
        context: str = DEFAULT_CONTEXT,
    ) -> str:
        """Wait for something to happen before going on.

        what is visible or hidden (value is the element, by as in find), url
        (value is part of the address), load (value is load, domcontentloaded
        or networkidle; load by default) or response (value is part of the
        address of a response). Waits seconds at most.

        Wartet, bis etwas eintritt: visible oder hidden (ein Element), url
        (Teil der Adresse), load (Ladezustand) oder response (Teil der Adresse
        einer Antwort), höchstens seconds Sekunden.

        Stichworte: warten auf, bis Element erscheint, verschwindet, geladen.
        """
        return await reading.wait_until(
            space.browsing(context), what, value, by, seconds
        )

    return [read, screenshot, wait_until]


def _keeping(space: Workspace) -> list[Tool]:
    """Return the tools for cookies, storage, requests and the contexts."""

    async def storage(
        kind: str = "cookies",
        action: str = "get",
        key: str = "",
        value: str = "",
        context: str = DEFAULT_CONTEXT,
    ) -> str:
        """Read, set or clear the cookies or the local storage of a context.

        kind is cookies or local, action is get, set or clear. For cookies, set
        takes a JSON object or array in value, each with name, value and domain
        or url; key is not used. For local, key names the entry and value is
        what goes in; get without key returns everything. Cookies belong to
        the context, the local storage to the origin of the open page.

        Liest, setzt oder löscht Cookies (kind=cookies) oder den Local Storage
        (kind=local) eines Kontexts; action ist get, set oder clear.

        Stichworte: Cookies, Local Storage, Browserspeicher, Anmeldung
        übernehmen.
        """
        return await keep.storage(space.browsing(context), kind, action, key, value)

    async def intercept(
        action: str,
        pattern: str,
        body: str = "",
        status: int = 200,
        context: str = DEFAULT_CONTEXT,
    ) -> str:
        """Interfere with requests the page makes: answer, block, or stop.

        action is mock, abort or clear; pattern is a glob such as **/api/**.
        mock answers matching requests with body and status, abort blocks them,
        clear lets them through again.

        Greift in Anfragen der Seite ein: mock beantwortet passende Anfragen
        mit body und status, abort blockiert sie, clear lässt sie wieder durch.

        Stichworte: Anfrage abfangen, Antwort vortäuschen, blockieren, mocken.
        """
        return await keep.intercept(
            space.browsing(context), action, pattern, body, status
        )

    async def contexts(action: str = "list", name: str = "") -> str:
        """List the open browser contexts, or close one or all of them.

        action is list or close. list names each context with its tabs and how
        long nobody has used it. close with name closes that context, without
        name every context and the browser; do that when finished, it frees
        memory.

        Listet die offenen Browser-Kontexte oder schließt einen oder alle.
        Ohne name schließt close alle und beendet den Browser; das gibt
        Speicher frei.

        Stichworte: Browser-Kontexte, Sitzungen, Browser schließen, aufräumen.
        """
        return await keep.contexts(space, action, name)

    return [storage, intercept, contexts]
