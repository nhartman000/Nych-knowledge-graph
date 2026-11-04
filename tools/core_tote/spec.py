"""Hand-authored CORE TOTE loop specs for basic software / AI-tool functions.

Each spec describes ONE declared function performing as intended (not an agent):
precondition test -> one operation -> observable post-condition test -> exit,
with bounded retry/stop. `q` = regexes that ALL must match a cached official help
quote for it to count as grounding; `v` = independent second-pass terms (any one
must appear in quote or section) used by verify.py.
"""
from __future__ import annotations

# retry policy classes: idempotent ops may retry; non-idempotent ops never auto-retry
IDEMP = 2      # max retries (3 attempts total)
ONCE = 0       # non-idempotent / irreversible: no automatic retry

S = []


def F(fid, cat, canon, name, pre, op, post, fail, q, v, retries=IDEMP, variants=None, sec=None):
    S.append(dict(id=fid, category=cat, canonical_action=canon, name=name, pre=pre, op=op,
                  post=post, fail=fail, q=q, v=v, max_retries=retries, variants=variants or {}, sec=sec))


KB = lambda win, mac, extra=None: dict({"windows": win, "macos": mac}, **(extra or {}))

# ---------------- files & folders ----------------
F("FILE_OPEN", "files", "OPEN_FILE", "Open a file",
  "The file is visible in the file manager or app's file list and is not already open.",
  "Open the selected file (double-click, tap, or Open command).",
  "The file's contents are displayed in an application window/tab titled with the file name.",
  "Error dialog (unsupported type, missing file, no permission) or no window appears.",
  [r"\bopen\b", r"\bfiles?\b"], ["open"])
F("FILE_CREATE_FOLDER", "files", "CREATE_ITEM", "Create a new folder",
  "The current location is writable (New folder / Create control is enabled).",
  "Invoke New folder and enter a folder name.",
  "A folder with the entered name is listed in the current location.",
  "Name rejected (invalid characters/duplicate) or permission error.",
  [r"new folder|create (a )?(new )?folder"], ["folder"],
  variants=KB("File Explorer: Ctrl+Shift+N", "Finder: Shift+Command+N"))
F("FILE_RENAME", "files", "EDIT_ITEM", "Rename a file or folder",
  "Exactly one item is selected and is not open/locked by another app.",
  "Invoke Rename, type the new name, and confirm.",
  "The item is listed under the new name and the old name no longer appears.",
  "Name rejected, item in use, or permission denied.",
  [r"\brenam"], ["renam"], variants=KB("File Explorer: F2", "Finder: select item, press Return"))
F("FILE_DELETE", "files", "DELETE_ITEM", "Delete a file or folder (to trash/recycle bin)",
  "The item(s) to delete are selected and the location permits deletion.",
  "Invoke Delete on the selection.",
  "The item is no longer listed in its location (and appears in Trash/Recycle Bin/Bin where the platform has one).",
  "Permission error, item in use, or confirmation declined.",
  [r"\bdelet", r"files?|folders?|photos?|items?"], ["delet"], retries=ONCE,
  variants=KB("File Explorer: Delete key -> Recycle Bin", "Finder: Command+Delete -> Trash"))
F("FILE_RESTORE_TRASH", "files", "BACKUP_RESTORE", "Restore an item from Trash / Recycle Bin",
  "The deleted item is listed in Trash/Recycle Bin/Bin and its retention period has not expired.",
  "Select the item and invoke Restore (Put Back).",
  "The item no longer appears in Trash and is listed in its original location.",
  "Item missing from Trash (expired/emptied) or restore error.",
  [r"\brestor", r"trash|recycle bin|\bbin\b"], ["restor"],
  variants=KB("Recycle Bin: Restore", "Trash: Put Back"))
F("FILE_EMPTY_TRASH", "files", "DELETE_ITEM", "Empty Trash / Recycle Bin",
  "Trash/Recycle Bin contains at least one item the user has decided to permanently remove.",
  "Invoke Empty Trash / Empty Recycle Bin and confirm.",
  "Trash/Recycle Bin shows no items.",
  "Confirmation declined or an item cannot be removed.",
  [r"\bempty\b", r"trash|recycle bin|\bbin\b"], ["empty"], retries=ONCE)
F("FILE_MOVE", "files", "MOVE_ITEM", "Move a file or folder to another folder",
  "Source item selected; destination folder exists and is writable.",
  "Invoke Move (or drag the item) to the destination folder.",
  "The item is listed in the destination and no longer in the source location.",
  "Name conflict prompt, permission error, or destination unavailable.",
  [r"\bmove\b", r"files?|folders?|items?|photos?"], ["move"])
F("FILE_COPY", "files", "COPY", "Copy selected item(s) to the clipboard",
  "One or more items or a text range is selected.",
  "Invoke Copy.",
  "Paste becomes available and pasting reproduces the selection; the source is unchanged.",
  "Copy command disabled (nothing selected or content protected).",
  [r"\bcopy\b"], ["copy"], variants=KB("Ctrl+C", "Command+C", {"android/ios": "long-press, then Copy"}))
F("FILE_PASTE", "files", "PASTE", "Paste clipboard contents",
  "The clipboard holds content and the focused target accepts that content type.",
  "Invoke Paste at the target location/cursor.",
  "The clipboard content appears at the target.",
  "Paste disabled or content type rejected.",
  [r"\bpaste\b"], ["paste"], variants=KB("Ctrl+V", "Command+V", {"android/ios": "long-press, then Paste"}))
F("FILE_CUT", "text_editing", "CUT", "Cut a selection",
  "A text range or item is selected in an editable location.",
  "Invoke Cut.",
  "The selection is removed from its location and is available to Paste.",
  "Cut disabled (read-only or nothing selected).",
  [r"\bcut\b"], ["cut"], variants=KB("Ctrl+X", "Command+X"))
F("FILE_DOWNLOAD", "files", "DOWNLOAD", "Download a file to the device",
  "A downloadable file or Download control is visible and the device has storage space.",
  "Invoke Download on the item.",
  "The file appears in the downloads list/folder with completed status.",
  "Download blocked, failed, or interrupted.",
  [r"\bdownload"], ["download"])
F("FILE_UPLOAD", "files", "UPLOAD_FILE", "Upload a file to cloud storage",
  "Signed in to the storage service; the local file exists; destination folder is writable.",
  "Invoke Upload (or New > File upload) and choose the file.",
  "The uploaded file is listed in the destination folder with upload complete.",
  "Upload error, quota exceeded, or file type/size rejected.",
  [r"\bupload"], ["upload"])
F("FILE_SHARE_LINK", "files", "SHARE_SEND", "Share a file with a person or by link",
  "The user owns or can share the file; the recipient address or link setting is decided.",
  "Invoke Share, enter the recipient (or set link access), and confirm.",
  "The recipient is listed with the chosen access (or the link setting shows the chosen access).",
  "Sharing blocked by policy or invalid address.",
  [r"\bshare\b", r"files?|folders?|links?|people|document"], ["share"], retries=ONCE)
F("FILE_SEARCH", "files", "SEARCH", "Search for a file by name or content",
  "The search box of the file manager/storage app is available.",
  "Type the search term into the search box and submit.",
  "A results list is displayed (possibly empty) for that term.",
  "Search unavailable or indexing error.",
  [r"\bsearch\b", r"files?|drive|folders?"], ["search"])
F("FILE_ZIP", "files", "USE_FEATURE", "Compress (zip) files",
  "One or more items are selected in the file manager.",
  "Invoke Compress / Send to > Compressed (zipped) folder.",
  "A .zip archive appears in the same location.",
  "Error dialog or insufficient space.",
  [r"\bzip|compress"], ["zip", "compress"])
F("FILE_SAVE", "text_editing", "SAVE", "Save the current document",
  "A document with changes is open in an editor that supports Save.",
  "Invoke Save (choose a name/location on first save).",
  "The title bar/status shows the document saved; reopening shows the changes.",
  "Save dialog cancelled, permission denied, or disk full.",
  [r"\bsave\b"], ["save"], variants=KB("Ctrl+S", "Command+S", {"web (Docs/Office for web)": "saves automatically"}))
F("FILE_PRINT", "files", "PRINT", "Print a document",
  "A document is open and a printer is available.",
  "Invoke Print, choose printer and settings, confirm.",
  "The print job appears in the print queue or the printer outputs the pages.",
  "No printer, printer offline, or job error.",
  [r"\bprint"], ["print"], retries=ONCE, variants=KB("Ctrl+P", "Command+P"))
F("FILE_EXPORT_PDF", "files", "EXPORT_IMPORT", "Export/download a document as PDF",
  "A document is open in an app offering PDF export.",
  "Invoke Download/Export/Save as > PDF.",
  "A .pdf file exists at the chosen location/downloads.",
  "Export option missing or export error.",
  [r"\bpdf\b"], ["pdf"])
F("SCREENSHOT", "files", "SCAN_CAPTURE", "Take a screenshot",
  "The content to capture is on screen.",
  "Invoke the platform screenshot command.",
  "A screenshot image is saved (thumbnail/notification appears; file in Screenshots/Pictures).",
  "No capture feedback (content protected or command not recognized).",
  [r"screenshot|screen capture|snipping"], ["screenshot", "snip", "capture"],
  variants=KB("Windows key+Shift+S (Snipping Tool)", "Shift+Command+3/4", {"android": "Power+Volume down"}))

# ---------------- text editing ----------------
F("TEXT_SELECT_ALL", "text_editing", "SELECT_ITEM", "Select all content",
  "Focus is in a document, field, or list.",
  "Invoke Select All.",
  "All content in the focused area is highlighted.",
  "Nothing highlighted.",
  [r"select all"], ["select all"], variants=KB("Ctrl+A", "Command+A"))
F("TEXT_UNDO", "text_editing", "UNDO_REDO", "Undo the last action",
  "At least one undoable action exists (Undo enabled).",
  "Invoke Undo once.",
  "The most recent change is reverted.",
  "Undo disabled/nothing to undo.",
  [r"\bundo\b"], ["undo"], retries=ONCE, variants=KB("Ctrl+Z", "Command+Z"))
F("TEXT_REDO", "text_editing", "UNDO_REDO", "Redo an undone action",
  "Redo is enabled (an undo was just performed).",
  "Invoke Redo once.",
  "The undone change is re-applied.",
  "Redo disabled.",
  [r"\bredo\b"], ["redo"], retries=ONCE, variants=KB("Ctrl+Y", "Shift+Command+Z"))
F("TEXT_FIND", "text_editing", "SEARCH", "Find text in a document or page",
  "A document or page is open.",
  "Open Find, type the search text.",
  "Matches are highlighted and a match count/next control shows (or 'no results').",
  "Find bar does not open.",
  [r"\bfind\b", r"ctrl|command|text|word|page|document"], ["find"], variants=KB("Ctrl+F", "Command+F"))
F("TEXT_REPLACE", "text_editing", "EDIT_ITEM", "Find and replace text",
  "A document is open and editable.",
  "Open Find and replace, enter find text and replacement, invoke Replace/Replace all.",
  "Occurrences are replaced and the app reports the replacement (count or updated text).",
  "No matches found or document read-only.",
  [r"replace"], ["replace"], retries=ONCE, variants=KB("Ctrl+H", "Command+Shift+H (Docs) / varies by app"))
F("TEXT_BOLD", "text_editing", "SET_VALUE", "Apply bold formatting",
  "Text is selected in a rich-text editor.",
  "Invoke Bold.",
  "The selected text renders bold and the Bold control shows active.",
  "Format control disabled.",
  [r"\bbold\b"], ["bold"], variants=KB("Ctrl+B", "Command+B"))
F("TEXT_FONT_SIZE", "text_editing", "SET_VALUE", "Change font or text size",
  "Text is selected (or the setting is app-wide).",
  "Choose a font / size value.",
  "Text renders in the chosen font/size and the control shows the value.",
  "Value rejected or control disabled.",
  [r"\bfont|text size"], ["font", "text size"])
F("TEXT_SPELLCHECK", "text_editing", "USE_FEATURE", "Accept a spelling suggestion",
  "A word is flagged as misspelled.",
  "Open the suggestion for that word and choose a correction.",
  "The word is replaced and no longer flagged.",
  "No suggestions available.",
  [r"spell"], ["spell"])
F("TEXT_INSERT_LINK", "text_editing", "ADD_ITEM", "Insert a hyperlink",
  "Text or cursor position is selected in an editor supporting links.",
  "Invoke Insert link, enter URL, apply.",
  "The text displays as a link and opening it targets the URL.",
  "URL rejected.",
  [r"\blinks?\b", r"insert|add"], ["link"], variants=KB("Ctrl+K", "Command+K"))
F("TEXT_INSERT_IMAGE", "text_editing", "ADD_ITEM", "Insert an image into a document",
  "A document is open and editable.",
  "Invoke Insert > Image and choose the image.",
  "The image appears in the document at the cursor.",
  "File type unsupported or upload fails.",
  [r"insert", r"image|picture|photo"], ["insert"])
F("TEXT_COMMENT", "text_editing", "ADD_ITEM", "Add a comment to a document",
  "Text is selected in a document where the user can comment.",
  "Invoke Add comment, type it, and post.",
  "The comment appears in the margin/comment pane anchored to the selection.",
  "Comment control disabled (view-only).",
  [r"comment"], ["comment"], retries=ONCE)
F("TEXT_TRACK_CHANGES", "text_editing", "TOGGLE_ON", "Turn on Track Changes / Suggesting",
  "A document is open with edit rights.",
  "Toggle Track Changes (Word) or switch to Suggesting mode (Docs).",
  "The mode indicator shows tracking/suggesting is on.",
  "Option unavailable.",
  [r"track changes|suggesting"], ["track", "suggest"])
F("TEXT_VERSION_HISTORY", "text_editing", "OPEN_ITEM", "Open version history",
  "A cloud document is open with edit rights.",
  "Invoke Version history.",
  "A list of earlier versions with dates is displayed.",
  "Option unavailable.",
  [r"version history|previous version"], ["version"])
F("TEXT_DICTATE", "text_editing", "VOICE_COMMAND", "Dictate text with voice typing",
  "A text field has focus and a microphone is available and permitted.",
  "Start dictation/voice typing and speak.",
  "Spoken words appear as text in the field.",
  "Microphone denied or no speech recognized.",
  [r"dictat|voice typing"], ["dictat", "voice typing"], variants={"windows": "Windows key+H"})

# ---------------- browser ----------------
F("BR_OPEN_URL", "browser", "OPEN_WEBPAGE", "Open a web address",
  "A browser window is open and online.",
  "Type the URL in the address bar and press Enter.",
  "The page loads and the address bar shows the URL.",
  "Error page (no connection, DNS, certificate).",
  [r"address bar|\burl\b"], ["address bar", "url"])
F("BR_NEW_TAB", "browser", "OPEN_TAB_PANEL", "Open a new tab",
  "A browser window is open.",
  "Invoke New tab.",
  "A new tab is shown and selected.",
  "No new tab appears.",
  [r"new tab"], ["new tab"], variants=KB("Ctrl+T", "Command+T"))
F("BR_CLOSE_TAB", "browser", "CLOSE_ITEM", "Close a tab",
  "The target tab is open.",
  "Invoke Close on the tab.",
  "The tab is no longer in the tab strip.",
  "Page blocks with an unsaved-changes prompt (stop; do not override).",
  [r"close", r"\btabs?\b"], ["close"], retries=ONCE, variants=KB("Ctrl+W", "Command+W"))
F("BR_REOPEN_TAB", "browser", "OPEN_TAB_PANEL", "Reopen a closed tab",
  "A tab was closed in this session.",
  "Invoke Reopen closed tab.",
  "The last closed tab reappears with its page.",
  "Nothing to reopen.",
  [r"reopen|closed tab"], ["reopen", "closed"], retries=ONCE, variants=KB("Ctrl+Shift+T", "Command+Shift+T"))
F("BR_BOOKMARK", "browser", "KEEP_REMEMBER", "Bookmark the current page",
  "A page is loaded.",
  "Invoke Bookmark this page (star) and confirm.",
  "The star is filled and the page is listed in bookmarks.",
  "Bookmark not saved.",
  [r"bookmark|favorite"], ["bookmark", "favorite"], variants=KB("Ctrl+D", "Command+D"))
F("BR_RELOAD", "browser", "REFRESH_RELOAD", "Reload the page",
  "A page is loaded or failed to load.",
  "Invoke Reload.",
  "The page is re-requested and re-rendered.",
  "Same error persists after reload.",
  [r"reload|refresh"], ["reload", "refresh"], variants=KB("F5 or Ctrl+R", "Command+R"))
F("BR_BACK", "browser", "GO_BACK", "Go back to the previous page",
  "The tab has a previous history entry (Back enabled).",
  "Invoke Back.",
  "The previous page is displayed.",
  "Back disabled.",
  [r"\bback\b", r"arrow|button|page|go back|tap back|select back"], ["back"], retries=ONCE)
F("BR_PRIVATE", "browser", "OPEN_TAB_PANEL", "Open a private (Incognito/InPrivate) window",
  "The browser is open.",
  "Invoke New Incognito/InPrivate window.",
  "A window with the private-mode indicator opens.",
  "Private mode disabled by policy.",
  [r"incognito|inprivate|private (window|browsing)"], ["incognito", "inprivate", "private"],
  variants={"chrome": "Ctrl+Shift+N / Command+Shift+N (Incognito)", "edge": "Ctrl+Shift+N (InPrivate)"})
F("BR_CLEAR_DATA", "browser", "DELETE_ITEM", "Clear browsing data (cache/cookies/history)",
  "Browser settings are reachable; the user has chosen data types and time range.",
  "Open Clear browsing data, choose types and range, confirm.",
  "The browser reports data cleared; history/cache for the range is empty.",
  "Clearing blocked or sync profile prompt.",
  [r"clear|delete", r"cache|cookies|browsing data|history"], ["clear", "delete"], retries=ONCE,
  variants={"chrome/edge (desktop)": "Ctrl+Shift+Delete"})
F("BR_HISTORY", "browser", "OPEN_ITEM", "View browsing history",
  "The browser is open.",
  "Open History.",
  "A dated list of visited pages is shown.",
  "History empty or disabled.",
  [r"\bhistory\b"], ["history"], variants=KB("Ctrl+H", "Command+Y"))
F("BR_ZOOM", "browser", "SET_VALUE", "Zoom page in or out",
  "A page is loaded.",
  "Invoke Zoom in/out once.",
  "Content renders larger/smaller and the zoom level indicator changes.",
  "Zoom at limit.",
  [r"\bzoom"], ["zoom"], variants=KB("Ctrl + / Ctrl -", "Command + / Command -"))
F("BR_DEFAULT_BROWSER", "browser", "SET_VALUE", "Set the default browser",
  "The browser is installed.",
  "Open OS default-apps settings and choose the browser.",
  "Settings show the browser as default for web links.",
  "Setting locked by policy.",
  [r"default browser"], ["default"])
F("BR_EXTENSION_ADD", "browser", "INSTALL_APP", "Add a browser extension",
  "The extension's store page is open and installs are allowed.",
  "Invoke Add to browser and confirm permissions.",
  "The extension icon/listing appears in the extensions menu.",
  "Install blocked by policy or error.",
  [r"extensions?|add-ons?"], ["extension", "add-on"], retries=ONCE)
F("BR_SAVE_PASSWORD", "browser", "TOGGLE", "Turn the browser's offer-to-save-passwords setting on or off",
  "The browser's password manager settings page is open.",
  "Toggle 'Offer to save passwords' to the chosen state.",
  "The toggle shows the chosen state.",
  "Setting managed by policy or sync account.",
  [r"password", r"save|saved|manager"], ["password"])

# ---------------- settings / device ----------------
F("SET_OPEN", "settings", "OPEN_SETTINGS", "Open Settings",
  "The device is unlocked.",
  "Open the Settings app/page.",
  "The Settings home is displayed.",
  "Settings does not open.",
  [r"\bsettings\b", r"open|go to|select|tap|launch"], ["settings"],
  variants={"windows": "Windows key+I", "macos": "Apple menu > System Settings", "android": "Settings app"})
F("SET_WIFI", "settings", "CONNECT_DEVICE", "Connect to a Wi-Fi network",
  "Wi-Fi hardware is on and the target network is listed.",
  "Select the network, enter its password if asked, connect.",
  "The network shows Connected and the Wi-Fi status icon appears.",
  "Wrong password / cannot connect.",
  [r"wi-?fi"], ["wi-fi", "wifi"])
F("SET_BLUETOOTH", "settings", "CONNECT_DEVICE", "Pair a Bluetooth device",
  "Bluetooth is on and the accessory is in pairing mode.",
  "Select the device in the Bluetooth list and confirm pairing.",
  "The device is listed as Connected/Paired.",
  "Pairing fails or device not found.",
  [r"bluetooth"], ["bluetooth"])
F("SET_AIRPLANE", "settings", "TOGGLE", "Toggle Airplane / Flight mode",
  "The device has radios and Quick Settings/Settings is open.",
  "Toggle Airplane (Flight) mode.",
  "The toggle shows the new state and the airplane icon appears/disappears.",
  "Toggle unavailable.",
  [r"airplane|flight mode"], ["airplane", "flight"])
F("SET_DARK_MODE", "settings", "SET_VALUE", "Switch to dark mode / theme",
  "Appearance settings are reachable.",
  "Choose Dark mode/theme.",
  "UI renders in dark colors and the setting shows Dark.",
  "Option unavailable.",
  [r"dark (mode|theme)"], ["dark"])
F("SET_BRIGHTNESS", "settings", "SET_VALUE", "Adjust screen brightness",
  "The display supports software brightness control.",
  "Move the brightness slider.",
  "Screen brightness changes and the slider shows the new level.",
  "Slider absent (external monitor).",
  [r"brightness"], ["brightness"])
F("SET_VOLUME", "settings", "SET_VALUE", "Adjust volume",
  "An audio output device is active.",
  "Move the volume slider or press volume keys.",
  "The volume indicator shows the new level.",
  "No output device.",
  [r"\bvolume\b"], ["volume"])
F("SET_NOTIFICATIONS", "settings", "TOGGLE_OFF", "Turn notifications off for an app",
  "The app is listed under notification settings.",
  "Toggle that app's notifications off.",
  "The app's notification toggle shows Off.",
  "Toggle managed by policy.",
  [r"notifications?", r"turn off|off|disable|allow|toggle|manage"], ["notification"])
F("SET_DND", "settings", "TOGGLE_ON", "Turn on Do Not Disturb / Focus",
  "Quick Settings or Focus settings is reachable.",
  "Toggle Do not disturb (Focus) on.",
  "The DND/Focus indicator is shown.",
  "Option unavailable.",
  [r"do not disturb|focus"], ["disturb", "focus"])
F("SET_LANGUAGE", "settings", "SET_VALUE", "Change display language",
  "Language settings are reachable; target language available.",
  "Add/select the language and set it as display language.",
  "Settings list it as display language (may require sign-out/restart to apply).",
  "Language pack download fails.",
  [r"language"], ["language"])
F("SET_DATE_TIME", "settings", "SET_VALUE", "Set date, time, or time zone",
  "Date & time settings are reachable.",
  "Set the time zone or toggle automatic time.",
  "The clock shows the expected time/zone.",
  "Setting locked.",
  [r"time zone|date and time|date & time"], ["time"])
F("SET_UPDATE", "settings", "UPDATE_SOFTWARE", "Check for and install system updates",
  "The device is online and has power/battery as required.",
  "Open software update and invoke Check for updates / Install.",
  "Update status shows up to date or an install/restart pending.",
  "Update download or install error.",
  [r"update", r"check|install|download"], ["update"], retries=ONCE)
F("SET_RESTART", "settings", "RESTART_DEVICE", "Restart the device",
  "Open work is saved.",
  "Invoke Restart.",
  "The device shuts down and boots back to the lock/sign-in screen.",
  "Restart blocked by an app or hangs.",
  [r"\brestart"], ["restart"], retries=ONCE)
F("SET_APP_INSTALL", "settings", "INSTALL_APP", "Install an app from the official store",
  "Signed in to the app store; app page open; storage available.",
  "Invoke Install/Get.",
  "The app shows Open/Installed and appears in the app list.",
  "Install error, incompatible device, or insufficient storage.",
  [r"\binstall"], ["install"], retries=ONCE)
F("SET_APP_UNINSTALL", "settings", "UNINSTALL_APP", "Uninstall an app",
  "The app is installed and removable.",
  "Invoke Uninstall on the app and confirm.",
  "The app no longer appears in the app list.",
  "Uninstall disabled (system app) or error.",
  [r"uninstall"], ["uninstall"], retries=ONCE)
F("SET_APP_FORCE_STOP", "settings", "CLOSE_ITEM", "Close / force-stop an unresponsive app",
  "The app is running.",
  "Close the app (Task Manager End task, Force Quit, or Force stop).",
  "The app no longer appears among running apps.",
  "App reappears immediately (stop; report).",
  [r"force stop|force quit|end task|close (the )?app"], ["force", "end task", "close"], retries=ONCE)
F("SET_PERMISSION", "settings", "ALLOW_PERMISSION", "Grant or revoke an app permission",
  "The app is listed under app permissions.",
  "Set the permission (camera, microphone, location...) to Allow or Deny.",
  "The permission shows the chosen value.",
  "Permission managed by policy.",
  [r"permission"], ["permission"])
F("SET_STORAGE_CHECK", "settings", "VERIFY_STATE", "Check storage space",
  "Storage settings are reachable.",
  "Open Storage settings.",
  "Used/available storage is displayed.",
  "Storage info unavailable.",
  [r"storage"], ["storage"])
F("SET_BACKUP", "settings", "BACKUP_RESTORE", "Back up device or data",
  "Signed in to the backup service with enough quota.",
  "Invoke Back up now.",
  "The backup shows a completion time of now.",
  "Backup fails or quota exceeded.",
  [r"back ?up"], ["back"], retries=ONCE)
F("SET_LOCK_SCREEN", "settings", "LOCK_UNLOCK", "Lock the device screen",
  "The device is unlocked.",
  "Invoke Lock.",
  "The lock screen is shown and unlocking requires credentials.",
  "Device does not lock.",
  [r"\block\b"], ["lock"], variants=KB("Windows key+L", "Control+Command+Q"))
F("SET_BATTERY_SAVER", "settings", "TOGGLE_ON", "Turn on battery/power saver",
  "Device runs on battery.",
  "Toggle Battery/Power saver on.",
  "The saver indicator shows On.",
  "Option unavailable.",
  [r"saver|power mode|low power"], ["saver", "power"])

# ---------------- accounts / sign-in ----------------
F("ACC_SIGN_IN", "accounts", "SIGN_IN", "Sign in to an account",
  "The sign-in page is open and the account's email/username and password are known.",
  "Enter identifier and password and submit (plus 2-step code if requested).",
  "The account name/avatar is shown as signed in.",
  "Wrong password, locked account, or verification failure.",
  [r"sign in|log in"], ["sign in", "log in"], retries=ONCE)
F("ACC_SIGN_OUT", "accounts", "SIGN_OUT", "Sign out of an account",
  "The user is signed in.",
  "Open the account menu and invoke Sign out.",
  "The sign-in prompt is shown and the avatar is gone.",
  "Sign-out option missing.",
  [r"sign out|log out"], ["sign out", "log out"], retries=ONCE)
F("ACC_CHANGE_PASSWORD", "accounts", "SET_VALUE", "Change account password",
  "Signed in; current password known (or re-auth available).",
  "Open security settings > Password, re-authenticate, enter and confirm a new password.",
  "The service confirms the password changed (and may sign out other sessions).",
  "New password rejected (strength/reuse) or re-auth fails.",
  [r"password", r"change|reset|new"], ["password"], retries=ONCE)
F("ACC_RESET_PASSWORD", "accounts", "RESET", "Recover / reset a forgotten password",
  "The account identifier is known and a recovery method (email/phone) is accessible.",
  "Invoke Forgot password, complete verification, set a new password.",
  "Sign-in with the new password succeeds.",
  "Verification fails; recovery unavailable.",
  [r"forgot|recover|reset", r"password|account"], ["password", "recover"], retries=ONCE)
F("ACC_2SV_ON", "accounts", "TOGGLE_ON", "Turn on 2-Step Verification / two-factor authentication",
  "Signed in; a second factor (phone/app/key) is available.",
  "Open security settings, start 2-Step Verification, enroll the factor.",
  "Security settings show 2-Step Verification On.",
  "Enrollment code rejected.",
  [r"2-step|two-step|two-factor|2fa|multi-factor"], ["2-step", "two-step", "two-factor", "factor"], retries=ONCE)
F("ACC_ENTER_CODE", "accounts", "ENTER_CODE", "Enter a verification code",
  "A verification-code prompt is shown and a code was received on the registered factor.",
  "Type the code and submit.",
  "The prompt closes and the next step/sign-in completes.",
  "Code rejected or expired.",
  [r"code"], ["code"], retries=ONCE)
F("ACC_CREATE", "accounts", "CREATE_ACCOUNT", "Create an account",
  "The sign-up page is open; the user has decided on name/identifier.",
  "Fill required sign-up fields and submit.",
  "The service shows the new account signed in or a verification email/code sent.",
  "Identifier taken or validation error.",
  [r"create", r"account"], ["account"], retries=ONCE)
F("ACC_SWITCH", "accounts", "SELECT_ITEM", "Switch between signed-in accounts",
  "Two or more accounts are signed in.",
  "Open the account switcher and choose the account.",
  "The active avatar/email shows the chosen account.",
  "Account requires re-sign-in.",
  [r"switch", r"accounts?|profiles?"], ["switch"])
F("ACC_PROFILE_PHOTO", "accounts", "EDIT_ITEM", "Change profile picture",
  "Signed in; an image is available.",
  "Open profile, choose Change photo, pick image, save.",
  "The new picture is shown on the profile/avatar.",
  "Image rejected.",
  [r"profile (picture|photo)|account picture"], ["profile", "picture", "photo"])
F("ACC_DELETE", "accounts", "DELETE_ITEM", "Delete an account",
  "Signed in; the user has explicitly decided to delete; re-auth available.",
  "Open account data settings, invoke Delete account, confirm.",
  "The service confirms deletion (or scheduled deletion).",
  "Confirmation fails; deletion blocked.",
  [r"delete", r"account"], ["delete"], retries=ONCE)

# ---------------- messaging / email ----------------
F("MAIL_COMPOSE", "messaging", "CREATE_ITEM", "Start a new email",
  "Signed in to the mail app.",
  "Invoke Compose / New mail.",
  "An empty compose window with To/Subject/body fields opens.",
  "Compose does not open.",
  [r"compose|new (mail|message|email)"], ["compose", "new"])
F("MAIL_SEND", "messaging", "SHARE_SEND", "Send a composed email or message",
  "Compose window open with at least one valid recipient and content the user approved.",
  "Invoke Send once.",
  "The message appears in Sent (or the thread) and the compose window closes.",
  "Send error, invalid address; do NOT resend automatically (duplicate risk) — check Sent/Outbox first.",
  [r"\bsend\b"], ["send"], retries=ONCE)
F("MAIL_REPLY", "messaging", "SHARE_SEND", "Reply to a message",
  "The message is open.",
  "Invoke Reply (or Reply all), which opens a reply draft.",
  "A reply draft addressed to the sender (or all) is open with the original quoted/linked.",
  "Reply disabled.",
  [r"\breply\b"], ["reply"])
F("MAIL_FORWARD", "messaging", "SHARE_SEND", "Forward a message",
  "The message is open.",
  "Invoke Forward, which opens a draft containing the original.",
  "A forward draft with empty To and the original content is open.",
  "Forward disabled.",
  [r"\bforward"], ["forward"])
F("MAIL_ATTACH", "messaging", "UPLOAD_FILE", "Attach a file to an email",
  "Compose window open; file accessible and under the size limit.",
  "Invoke Attach and choose the file.",
  "The attachment chip with file name appears in the draft.",
  "File too large/blocked type.",
  [r"attach"], ["attach"])
F("MAIL_ARCHIVE", "messaging", "MOVE_ITEM", "Archive a message",
  "The message is selected or open.",
  "Invoke Archive.",
  "The message leaves the Inbox and is findable in All Mail/Archive.",
  "Archive unavailable.",
  [r"archiv"], ["archiv"])
F("MAIL_DELETE", "messaging", "DELETE_ITEM", "Delete a message",
  "The message is selected or open.",
  "Invoke Delete.",
  "The message is in Trash/Deleted Items and not in its folder.",
  "Delete fails.",
  [r"delet", r"messages?|emails?|conversations?|chats?"], ["delet"], retries=ONCE)
F("MAIL_MARK_SPAM", "messaging", "MOVE_ITEM", "Report a message as spam / junk",
  "The message is selected or open.",
  "Invoke Report spam / Junk.",
  "The message moves to Spam/Junk.",
  "Option unavailable.",
  [r"spam|junk"], ["spam", "junk"], retries=ONCE)
F("MAIL_SEARCH", "messaging", "SEARCH", "Search mail",
  "Signed in to the mail app.",
  "Type a query in the mail search box and submit.",
  "Matching messages are listed (or 'no results').",
  "Search fails.",
  [r"search", r"mail|messages?|inbox|emails?"], ["search"])
F("MAIL_LABEL", "messaging", "SET_VALUE", "Apply a label / move to a folder",
  "The message is selected; the label/folder exists.",
  "Invoke Label as / Move to and choose it.",
  "The message shows the label or is listed in the folder.",
  "Label/folder missing.",
  [r"label|folder"], ["label", "folder"])
F("MAIL_SIGNATURE", "messaging", "SET_VALUE", "Set an email signature",
  "Mail settings reachable.",
  "Open signature settings, enter text, save.",
  "New compose windows include the signature.",
  "Save fails.",
  [r"signature"], ["signature"])
F("MAIL_VACATION", "messaging", "TOGGLE_ON", "Turn on automatic replies / vacation responder",
  "Mail settings reachable.",
  "Enable vacation responder/automatic replies with dates and message; save.",
  "Settings show the responder on for the dates.",
  "Save fails.",
  [r"vacation|automatic repl|out of office"], ["vacation", "automatic", "office"])
F("MAIL_BLOCK", "messaging", "SET_VALUE", "Block a sender / contact",
  "A message or profile from the sender is open.",
  "Invoke Block and confirm.",
  "The sender appears in the blocked list.",
  "Option unavailable.",
  [r"\bblock"], ["block"], retries=ONCE)
F("MSG_UNSEND", "messaging", "CANCEL_ACTION", "Undo send / unsend within the allowed window",
  "A message was just sent and the Undo/unsend control is still displayed.",
  "Invoke Undo (unsend) once.",
  "The message returns to a draft/compose state or is shown as unsent.",
  "Window expired (stop; cannot recall).",
  [r"undo send|unsend|recall"], ["undo", "unsend", "recall"], retries=ONCE)
F("CAL_EVENT", "messaging", "CREATE_ITEM", "Create a calendar event",
  "Signed in to the calendar; date/time decided.",
  "Invoke Create/New event, enter title and time, save.",
  "The event appears on the calendar at the time.",
  "Save fails or time conflict prompt (stop for decision).",
  [r"event", r"create|add|new"], ["event"], retries=ONCE)
F("CONTACT_ADD", "messaging", "ADD_ITEM", "Add a contact",
  "The contacts app is open.",
  "Invoke Create/Add contact, enter details, save.",
  "The contact is listed.",
  "Save fails.",
  [r"contact", r"add|create|new"], ["contact"], retries=ONCE)

# ---------------- AI chat tools ----------------
F("AI_NEW_CHAT", "ai_chat", "CREATE_ITEM", "Start a new chat",
  "Signed in to the AI assistant.",
  "Invoke New chat.",
  "An empty conversation with an empty prompt box is shown.",
  "Control missing.",
  [r"new (chat|conversation|topic)"], ["new"])
F("AI_SEND_PROMPT", "ai_chat", "PROMPT_AI", "Send a prompt",
  "A conversation is open and the prompt box contains the user's text.",
  "Invoke Send (or press Enter) once.",
  "The prompt appears in the conversation and a response begins streaming.",
  "Error (rate/usage limit, network); do not resend automatically — check whether the prompt posted.",
  [r"prompt|message|ask|type", r"send|enter|submit|type"], ["prompt", "message", "send", "ask"], retries=ONCE)
F("AI_ATTACH_FILE", "ai_chat", "UPLOAD_FILE", "Attach a file to a prompt",
  "A conversation is open; file type and size supported.",
  "Invoke attach/upload (paperclip or +) and choose the file.",
  "A file chip/thumbnail appears in the prompt box.",
  "Unsupported type or size limit.",
  [r"upload|attach", r"files?|images?|documents?|photos?|pdf"], ["upload", "attach"])
F("AI_STOP", "ai_chat", "CANCEL_ACTION", "Stop a response that is generating",
  "A response is streaming and the Stop control is shown.",
  "Invoke Stop.",
  "Streaming halts; the partial response remains.",
  "Stop control absent (already finished).",
  [r"\bstop\b", r"respons|generat|answer"], ["stop"], retries=ONCE)
F("AI_REGENERATE", "ai_chat", "REFRESH_RELOAD", "Regenerate / retry a response",
  "The conversation has a completed assistant response.",
  "Invoke Retry/Regenerate on that response once.",
  "A new response is generated for the same prompt (alternate version shown).",
  "Control missing or error.",
  [r"regenerat|retry|redo|try again|draft"], ["regenerat", "retry", "redo", "draft"], retries=ONCE)
F("AI_COPY_RESPONSE", "ai_chat", "COPY", "Copy a response",
  "A completed response is displayed.",
  "Invoke Copy on the response.",
  "Pasting elsewhere reproduces the response text.",
  "Copy control missing.",
  [r"\bcopy\b"], ["copy"])
F("AI_EDIT_PROMPT", "ai_chat", "EDIT_ITEM", "Edit a previously sent prompt",
  "A sent prompt is in the conversation and editing is supported.",
  "Invoke Edit on the prompt, change text, submit.",
  "The edited prompt shows and a new response is generated from it.",
  "Edit not available.",
  [r"\bedit", r"prompt|message|question"], ["edit"], retries=ONCE)
F("AI_FEEDBACK", "ai_chat", "SELECT_OPTION", "Rate a response (thumbs up/down)",
  "A completed response is displayed.",
  "Invoke thumbs up or thumbs down (optionally add a comment).",
  "The thumb control shows the selected state / feedback acknowledgment.",
  "Control missing.",
  [r"thumbs|feedback"], ["thumb", "feedback"], retries=ONCE)
F("AI_RENAME_CHAT", "ai_chat", "EDIT_ITEM", "Rename a chat",
  "The chat is listed in the history/sidebar.",
  "Invoke Rename on the chat, type a name, confirm.",
  "The chat is listed under the new name.",
  "Rename unavailable.",
  [r"renam"], ["renam"])
F("AI_DELETE_CHAT", "ai_chat", "DELETE_ITEM", "Delete a chat",
  "The chat is listed in history.",
  "Invoke Delete on the chat and confirm.",
  "The chat no longer appears in history.",
  "Delete fails.",
  [r"delet", r"chats?|conversations?|activity|history"], ["delet"], retries=ONCE)
F("AI_SHARE_CHAT", "ai_chat", "SHARE_SEND", "Share a chat by link",
  "A conversation is open and sharing is allowed.",
  "Invoke Share, create the link.",
  "A share link is created/copied and shown.",
  "Sharing disabled by plan/policy.",
  [r"\bshar", r"chats?|conversations?|links?"], ["shar"], retries=ONCE)
F("AI_SEARCH_CHATS", "ai_chat", "SEARCH", "Search past chats",
  "Signed in; chat history exists.",
  "Open chat search and type a query.",
  "Matching chats are listed.",
  "Search unavailable.",
  [r"search", r"chats?|conversations?|history"], ["search"])
F("AI_VOICE_INPUT", "ai_chat", "VOICE_COMMAND", "Speak a prompt with voice input",
  "Microphone available and permitted.",
  "Invoke the microphone/voice control and speak.",
  "Speech is transcribed into the prompt box or submitted as a voice turn.",
  "Mic denied; nothing recognized.",
  [r"microphone|voice|\bmic\b"], ["mic", "voice"])
F("AI_MODEL_SELECT", "ai_chat", "SELECT_OPTION", "Choose a model / mode",
  "The model or mode picker is shown.",
  "Open the picker and select an option.",
  "The picker shows the selected model/mode.",
  "Option unavailable on plan.",
  [r"\bmodel|\bmode\b"], ["model", "mode"])
F("AI_PROJECT", "ai_chat", "CREATE_ITEM", "Create a project / workspace for chats",
  "Signed in on a plan that supports projects.",
  "Invoke New/Create project, name it, confirm.",
  "The project is listed.",
  "Feature unavailable.",
  [r"projects?|notebook|gem"], ["project", "notebook", "gem"], retries=ONCE)
F("AI_CUSTOM_INSTRUCTIONS", "ai_chat", "SET_VALUE", "Set custom instructions / personal preferences",
  "Assistant settings reachable.",
  "Open personalization/preferences, enter instructions, save.",
  "Settings show the saved instructions.",
  "Save fails.",
  [r"instructions|preferences|personaliz"], ["instruction", "preference", "personal"])
F("AI_MEMORY_TOGGLE", "ai_chat", "TOGGLE", "Turn chat memory / history saving on or off",
  "Assistant privacy/memory settings reachable.",
  "Toggle the memory/activity setting.",
  "The toggle shows the chosen state.",
  "Managed by admin.",
  [r"memory|activity|chat history"], ["memory", "activity", "history"])
F("AI_EXPORT_DATA", "ai_chat", "EXPORT_IMPORT", "Export your chat data",
  "Signed in; account settings reachable.",
  "Invoke Export data and confirm.",
  "The service confirms an export is prepared (download link/email).",
  "Export unavailable.",
  [r"export"], ["export"], retries=ONCE)
F("AI_GENERATE_IMAGE", "ai_chat", "PROMPT_AI", "Ask the assistant to create an image",
  "The assistant supports image generation for this account.",
  "Send a prompt requesting an image.",
  "An image appears in the response.",
  "Refusal or feature unavailable.",
  [r"image", r"creat|generat|make"], ["image"], retries=ONCE)
F("AI_UPLOAD_SCREENSHOT", "ai_chat", "SCAN_CAPTURE", "Add a screenshot / photo with the camera",
  "Camera or screen-capture permission granted.",
  "Invoke camera/screenshot in the prompt box and capture.",
  "The image appears attached in the prompt box.",
  "Permission denied.",
  [r"camera|screenshot|photo"], ["camera", "screenshot", "photo"])

# Section-heading regexes: the cached help article section must be ABOUT this
# function (strong grounding); the quote must match `q`. Applied by build.py.
SEC = {
 "FILE_OPEN": r"open (a |your )?files?|find & open files|open drive", "FILE_CREATE_FOLDER": r"create (a )?(new )?folder|new folder",
 "FILE_RENAME": r"rename (a |your )?(file|folder|files)", "FILE_DELETE": r"delete (a |your )?(file|folder|files)",
 "FILE_RESTORE_TRASH": r"restore", "FILE_EMPTY_TRASH": r"empty|permanently delete",
 "FILE_MOVE": r"move (a |your )?(file|folder|files|items)", "FILE_COPY": r"copy (and|&) paste|clipboard|copy (a |your )?(file|text)",
 "FILE_PASTE": r"copy (and|&) paste|paste", "FILE_CUT": r"\bcut\b|keyboard shortcuts", "FILE_DOWNLOAD": r"download (a |your )?(file|files)",
 "FILE_UPLOAD": r"upload (files|a file|or create|files & folders)", "FILE_SHARE_LINK": r"share (a |your )?(file|folder|files)|sharing",
 "FILE_SEARCH": r"(search|find) (for )?(files|in drive)|find files|search field", "FILE_ZIP": r"\bzip|compress",
 "FILE_SAVE": r"\bsave\b", "FILE_PRINT": r"\bprint", "FILE_EXPORT_PDF": r"pdf|download.*(as|format)|export",
 "SCREENSHOT": r"screenshot|snip", "TEXT_SELECT_ALL": r"select|shortcut", "TEXT_UNDO": r"undo|shortcut", "TEXT_REDO": r"redo|shortcut",
 "TEXT_FIND": r"\bfind\b.*(text|page|word)|find on page|search (a )?(document|page)|shortcut", "TEXT_REPLACE": r"find and replace|replace text",
 "TEXT_BOLD": r"format|bold", "TEXT_FONT_SIZE": r"font|text size", "TEXT_SPELLCHECK": r"spell", "TEXT_INSERT_LINK": r"insert links?|add (a )?links?|hyperlink",
 "TEXT_INSERT_IMAGE": r"insert|picture|image", "TEXT_COMMENT": r"comment", "TEXT_TRACK_CHANGES": r"track|suggest",
 "TEXT_VERSION_HISTORY": r"version", "TEXT_DICTATE": r"dictat|voice typing",
 "BR_OPEN_URL": r"address bar|open (a )?(web)?page|go to a (web)?site", "BR_NEW_TAB": r"new tab|open .*tab", "BR_CLOSE_TAB": r"close",
 "BR_REOPEN_TAB": r"reopen|closed tab|restore tab", "BR_BOOKMARK": r"add (a )?bookmark|favorite", "BR_RELOAD": r"reload|refresh (the )?page",
 "BR_BACK": r"go back|back button|navigate", "BR_PRIVATE": r"incognito|inprivate|private", "BR_CLEAR_DATA": r"(delete|clear).*(browsing|cache|cookies|history)",
 "BR_HISTORY": r"history", "BR_ZOOM": r"zoom", "BR_DEFAULT_BROWSER": r"default browser", "BR_EXTENSION_ADD": r"install (an )?extension|add (an )?extension|add-on",
 "BR_SAVE_PASSWORD": r"save.*password|password manager|saved passwords",
 "SET_OPEN": r"settings", "SET_WIFI": r"wi-?fi", "SET_BLUETOOTH": r"bluetooth", "SET_AIRPLANE": r"airplane|flight", "SET_DARK_MODE": r"dark",
 "SET_BRIGHTNESS": r"brightness", "SET_VOLUME": r"volume", "SET_NOTIFICATIONS": r"notification", "SET_DND": r"do not disturb|focus",
 "SET_LANGUAGE": r"(display|change|system|app) language|language setting|languages", "SET_DATE_TIME": r"date|time zone|clock",
 "SET_UPDATE": r"update", "SET_RESTART": r"restart", "SET_APP_INSTALL": r"install (an )?apps?|get apps|download apps",
 "SET_APP_UNINSTALL": r"uninstall|remove (an )?apps?|delete apps", "SET_APP_FORCE_STOP": r"close|force|stop|unresponsive|freez",
 "SET_PERMISSION": r"permission", "SET_STORAGE_CHECK": r"storage", "SET_BACKUP": r"back ?up", "SET_LOCK_SCREEN": r"lock",
 "SET_BATTERY_SAVER": r"saver|power mode|low power",
 "ACC_SIGN_IN": r"sign in to|log in to|sign in with|signing in", "ACC_SIGN_OUT": r"sign out|log out", "ACC_CHANGE_PASSWORD": r"change.*password",
 "ACC_RESET_PASSWORD": r"forgot|recover|reset.*password", "ACC_2SV_ON": r"2-step|two-step|two-factor|2fa|multi-factor",
 "ACC_ENTER_CODE": r"code|verif", "ACC_CREATE": r"create (a |an |your )?(google |microsoft )?account|sign up",
 "ACC_SWITCH": r"switch", "ACC_PROFILE_PHOTO": r"profile (picture|photo)|account picture", "ACC_DELETE": r"delete (your |an |a )?(google |claude )?account",
 "MAIL_COMPOSE": r"compose|write (an )?email|new (email|message)", "MAIL_SEND": r"send", "MAIL_REPLY": r"reply", "MAIL_FORWARD": r"forward (a|an|single|emails?|messages?)",
 "MAIL_ATTACH": r"attach", "MAIL_ARCHIVE": r"archive", "MAIL_DELETE": r"delete (one|messages?|emails?|conversation|a message)", "MAIL_MARK_SPAM": r"spam|junk",
 "MAIL_SEARCH": r"search", "MAIL_LABEL": r"label|folder", "MAIL_SIGNATURE": r"signature", "MAIL_VACATION": r"vacation|automatic repl|out of office",
 "MAIL_BLOCK": r"block", "MSG_UNSEND": r"undo send|unsend|recall", "CAL_EVENT": r"(create|add) (an )?event", "CONTACT_ADD": r"add (a )?contact|create (a )?contact",
 "AI_NEW_CHAT": r"new (chat|conversation)|start a chat|start", "AI_SEND_PROMPT": r"prompt|ask|chat|get started|message",
 "AI_ATTACH_FILE": r"upload|attach|files", "AI_STOP": r"stop", "AI_REGENERATE": r"regenerat|retry|redo", "AI_COPY_RESPONSE": r"copy|share|export",
 "AI_EDIT_PROMPT": r"edit", "AI_FEEDBACK": r"feedback|rate", "AI_RENAME_CHAT": r"rename", "AI_DELETE_CHAT": r"delete",
 "AI_SHARE_CHAT": r"share", "AI_SEARCH_CHATS": r"search|find", "AI_VOICE_INPUT": r"voice|dictat|microphone", "AI_MODEL_SELECT": r"model|mode",
 "AI_PROJECT": r"create (a )?project|projects?|gems?|notebook", "AI_CUSTOM_INSTRUCTIONS": r"instructions|preferences|personaliz",
 "AI_MEMORY_TOGGLE": r"memory|activity", "AI_EXPORT_DATA": r"export", "AI_GENERATE_IMAGE": r"image", "AI_UPLOAD_SCREENSHOT": r"screenshot|camera|photo",
}
for _s in S:
    _s["sec"] = SEC[_s["id"]]
