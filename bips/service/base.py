#REST webservice
import json
import os.path
import webbrowser

import cherrypy
from cherrypy.lib.static import serve_file
from cherrypy import expose

from ..workflows import get_workflows, get_workflow

class MyEncoder(json.JSONEncoder):
    def default(self, o):
        """Implement this method in a subclass such that it returns
        a serializable object for ``o``, or calls the base implementation
        (to raise a ``TypeError``).

        For example, to support arbitrary iterators, you could
        implement default like this::

            def default(self, o):
                try:
                    iterable = iter(o)
                except TypeError:
                    pass
                else:
                    return list(iterable)
                return JSONEncoder.default(self, o)

        """
        try:
            return super(MyEncoder, self).default(o)
        except TypeError:
            return ""

class BIPS:
    @expose
    def index(self):
        msg = ["<h2>Welcome to BIPS</h2>"]
        msg.append('<ul>')
        for wf, value in get_workflows():
            msg += ['<li><a href="info?uuid=%s">%s</a> %s</li>' % (wf, wf,
                                        value['object'].help.split('\n')[1])]
        msg.append('</li>')
        return '\n'.join(msg)

    @expose
    def info(self, uuid):
        wf = get_workflow(uuid)
        val = wf.get()
        json_str =  json.dumps(val, cls=MyEncoder)
        config_str = json.dumps(wf.config_ui().get(), cls=MyEncoder)
        img_file = ''
        msg = """
<!DOCTYPE html>
<html>
<head>
  <meta http-equiv="content-type" content="text/html; charset=UTF-8">
  <title> BIPS: Workflow info</title>
  <style type='text/css'>
    pre {outline: 1px solid #ccc; padding: 5px; margin: 5px; }
.string { color: green; }
.number { color: darkorange; }
.boolean { color: blue; }
.null { color: magenta; }
.key { color: red; }

  </style>
</head>
<body>

<script type="text/javascript">
function syntaxHighlight(json) {
    json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
        var cls = 'number';
        if (/^"/.test(match)) {
            if (/:$/.test(match)) {
                cls = 'key';
            } else {
                cls = 'string';
            }
        } else if (/true|false/.test(match)) {
            cls = 'boolean';
        } else if (/null/.test(match)) {
            cls = 'null';
        }
        return '<span class="' + cls + '">' + match + '</span>';
    });
}

var str = JSON.stringify(%s, null, 2);
document.write('<h3>Workflow info</h3>')
document.write('<pre>' + syntaxHighlight(str) +'</pre>');
var str2 = JSON.stringify(%s, null, 2);
document.write('<h3>Workflow config</h3>')
document.write('<pre>' + syntaxHighlight(str2) +'</pre>');
document.write('<h3>Workflow graph</h3>')
document.write('<img src="%s" />')
</script>

</body>


</html>
""" % (json_str, config_str, img_file)
        return msg

def open_page():
    webbrowser.open("http://127.0.0.1:8080/")

def start_service():
    MEDIA_DIR=os.path.join(os.path.dirname(__file__), 'scripts')
    #configure ip address and port for web service
    config = {'/scripts':
                      {'tools.staticdir.on': True,
                       'tools.staticdir.dir': MEDIA_DIR,
                       }
              }
    #start webservice
    cherrypy.engine.subscribe('start', open_page)
    cherrypy.tree.mount(BIPS(), '/', config=config)
    cherrypy.engine.start()
    cherrypy.engine.block()
    #cherrypy.quickstart(BIPS())