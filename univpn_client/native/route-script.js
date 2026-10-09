// Windows OpenConnect hook. Fixed helper/runtime paths provided by the guardian.
var shell = new ActiveXObject("WScript.Shell");
var env = shell.Environment("PROCESS");
var exe = env("UNIVPN_HELPER_EXE"), script = env("UNIVPN_HELPER_SCRIPT");
function quoted(value) {
    if (!value || value.indexOf('"') >= 0 || value.indexOf('\n') >= 0) throw new Error("Invalid helper path");
    return '"' + value + '"';
}
var command = quoted(exe) + (script ? " " + quoted(script) : "") + " --route-hook";
WScript.Quit(shell.Run(command, 0, true));
