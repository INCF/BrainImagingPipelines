#REST webservice
import json
import os
import shutil
from socket import gethostname
import webbrowser

import cherrypy
from cherrypy.lib.static import serve_file
from cherrypy import expose
import numpy as np

import lg_authority

from ..workflows import get_workflows, get_workflow
from scripts.form_scripts import get_form
from .demos.dicomconvert import unzip_and_extract

from mako.lookup import TemplateLookup, Template
from mako import exceptions


MEDIA_DIR = os.path.join(os.path.dirname(__file__), 'scripts')
FILE_DIR = os.path.join(os.getcwd(), 'files')

lookup = TemplateLookup(directories=[MEDIA_DIR], 
                        filesystem_checks=True, encoding_errors='replace',
                        strict_undefined=True)

if 'bips' in gethostname():
    url_prefix = '\/\/bips.incf.org:8080\/'
else:
    url_prefix = ''

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

@lg_authority.groups('auth')
class BIPS(object):
    auth = lg_authority.AuthRoot()

    def __init__(self, *args, **kwargs):
        tags = []
        mapper = {}
        workflows = {}
        for wf, value in get_workflows():
            wf_tags = sorted(np.unique([tag.lower() for tag in value['object'].tags]).tolist())
            for tag in wf_tags:
                if tag not in mapper:
                    mapper[tag] = []
                mapper[tag].append(wf)
            tags.extend(wf_tags)
            workflows[wf] = value['object'].help.split('\n')[1]
        self.tags_ = mapper.keys()
        self.mapper_ = mapper
        self.wf_ = workflows

    @expose
    def index(self):
        #with open(os.path.join(MEDIA_DIR, 'index.html')) as fp:
        #    msg = fp.readlines()
        indexTmpl = lookup.get_template("index.html")
        return indexTmpl.render()

    @expose
    def workflows(self, tags=None):
        #with open(os.path.join(MEDIA_DIR, 'workflows.html')) as fp:
        #    msg = fp.readlines()
        workflowTmpl = lookup.get_template("workflows.html")
        return workflowTmpl.render()

    @expose
    def edit_config(self,uuid='7757e3168af611e1b9d5001e4fb1404c'):
        conf = get_workflow(uuid).config_ui()
        mwf = get_workflow(uuid)
        title=mwf.help.split('\n')[1]
        desc = '\n'.join(mwf.help.split('\n')[3:])
        configTmpl = lookup.get_template("edit_config.html")
        return configTmpl.render(**{'form':get_form(conf),'WorkflowName':title,'WorkflowDesc':desc})
        #with open(os.path.join(MEDIA_DIR, 'edit_config.html')) as fp:
        #    m = fp.readlines()
        #    form = get_form(conf)
            
        #    msg = '\n'.join(m).replace('**TEMPLATE**',form)
        #return msg


    @expose
    def queryworkflows(self, tags=None):
        print tags
        cherrypy.response.headers['Content-Type'] = 'application/json'
        if tags:
            wfs = []
            for tag in tags.split():
                wfs.extend(self.mapper_[tag])
            return json.dumps([{'uuid': wf, 'desc': self.wf_[wf]} for wf in wfs])
        else:
            return json.dumps([{'uuid': uuid, 'desc': desc} for uuid, desc in self.wf_.items()])

    @expose
    def tags(self, query):
        tags = self.tags_
        if query:
            query = query.split()
            if len(query):
                pre = ' '.join(query[:-1])
                if pre:
                    pre += ' '
                query = query[-1]
            else:
                query = ' '
                pre=''
            tags = [pre + tag for tag in self.tags_ if query.lower() in tag]
        cherrypy.response.headers['Content-Type'] = 'application/json'
        return json.dumps(tags)

    @expose
    def info(self, uuid):
        wf = get_workflow(uuid)
        val = wf.get()
        json_str =  val #json.dumps(val, cls=MyEncoder)
        config_str = wf.config_ui().get() #json.dumps(wf.config_ui().get(), cls=MyEncoder)
        img_file = ''
        cherrypy.response.headers['Content-Type'] = 'application/json'
        return json.dumps({'jsonconfig': json_str, 'workflowconfig': config_str},
                          cls=MyEncoder)

    @expose
    def configure(self, uuid):
        wf = get_workflow(uuid)
        val = wf.get()

    @expose
    def demo(self):
        #with open(os.path.join(MEDIA_DIR, 'demo.html')) as fp:
        #    msg = fp.readlines()
        demoTmpl = lookup.get_template("demo_convert.html")
        return demoTmpl.render()

    @expose
    def demo_convert(self):
        demoTmpl = lookup.get_template("demo_convert.html")
        return demoTmpl.render()

    @expose
    def uploadhandler(self, **kwargs):
        if 'files[]' not in kwargs:
            return
        myFile = kwargs['files[]']
        outfile = os.path.join(FILE_DIR, myFile.filename)
        with open(outfile, 'wb') as fp:
            shutil.copyfileobj(myFile.file, fp)
        cherrypy.log('Saved file: %s' % outfile)
        if os.path.isfile(outfile):
            print "getting info: %s" % outfile
            size = os.path.getsize(outfile)
            from nibabel import load
            import Image
            import numpy as np
            data = load(outfile).get_data()
            if len(data.shape) == 4:
                slice = data[data.shape[0]/2,:,:,0]
            else:
                slice = data[data.shape[0]/2,:,:]
            print slice.shape
            im = Image.fromarray(np.squeeze(255.*slice/np.max(np.abs(slice))).astype(np.uint8))
            outpng = outfile+'.png'
            im.save(outpng)
            out = {"name": myFile.filename,
                   "size": size,
                   "url": "%sfiles\/%s" % (url_prefix, myFile.filename),
                   "thumbnail_url":"%sthumbnails\/%s.png" % (url_prefix, myFile.filename),
                   "delete_url": "%sdeletehandler?file=%s" % (url_prefix, myFile.filename),
                   "delete_type": "DELETE"
            }
        else:
            out = {}
        cherrypy.response.headers['Content-Type'] = 'application/json'
        return json.dumps([[out]])

    @expose
    def dicomuploadhandler(self, **kwargs):
        cherrypy.log('dcmhandler: %s' % str(kwargs))
        if 'files[]' not in kwargs:
            return
        myFile = kwargs['files[]']
        outfile = os.path.join(FILE_DIR, myFile.filename)
        with open(outfile, 'wb') as fp:
            shutil.copyfileobj(myFile.file, fp)
        cherrypy.log('Saved file: %s' % outfile)
        if os.path.isfile(outfile):
            print "getting info: %s" % outfile
            info = unzip_and_extract(outfile, FILE_DIR)
            os.unlink(outfile)
            print info
            out = []
            for key, value in sorted(info.items()):
                info = value
                out.append({"index": info['idx'],
                            "name": info['name'],
                            "metaname": info['metapath'],
                            'error': info['err_status'] == 'err',
                            "size": ' x '.join([str(val) for val in info['size']]),
                            "url": "%sfiles\/%s" % (url_prefix, info['filepath']),
                            "metaurl": "%sfiles\/%s" % (url_prefix, info['metapath']),
                            "delete_url": "%sdeletehandler?file=%s" % (url_prefix, info['filepath']),
                            "delete_type": "DELETE"
                })
            out = [out]
        else:
            out = {}
        print 'out', out
        cherrypy.response.headers['Content-Type'] = 'application/json'
        return json.dumps(out)

    @expose
    def deletehandler(self, file):
        outfile = os.path.join(FILE_DIR, file)
        if os.path.isfile(outfile):
            cherrypy.log('Deleting file: %s' % outfile)
            os.unlink(outfile)
            if os.path.exists(outfile + '.png'):
                os.unlink(outfile+'.png')
            if os.path.exists(outfile + '.json'):
                os.unlink(outfile+'.json')

def open_page():
    #pass
    webbrowser.open("http://127.0.0.1:8080")

def start_service():
    #configure ip address and port for web service
    if not os.path.exists(FILE_DIR):
        os.mkdir(FILE_DIR)
    config = {'/': {'tools.staticdir.on': True,
                    'tools.staticdir.dir': os.getcwd(),
                    'tools.lg_authority.on': False,
                    'tools.lg_authority.site_storage': 'sqlite3',
                    'tools.lg_authority.site_storage_conf':
                            { 'file': os.path.abspath('test.db') }
                    },
              '/css': {'tools.staticdir.on': True,
                       'tools.staticdir.dir': os.path.join(MEDIA_DIR, 'css')},
              '/js': {'tools.staticdir.on': True,
                      'tools.staticdir.dir': os.path.join(MEDIA_DIR, 'js')},
              '/cors': {'tools.staticdir.on': True,
                        'tools.staticdir.dir': os.path.join(MEDIA_DIR, 'cors')},
              '/img': {'tools.staticdir.on': True,
                       'tools.staticdir.dir': os.path.join(MEDIA_DIR, 'img')},
              '/thumbnails': {'tools.staticdir.on': True,
                       'tools.staticdir.dir': FILE_DIR},
              '/files': {'tools.staticdir.on': True,
                         'tools.staticdir.dir': FILE_DIR},
              '/scripts': {'tools.staticdir.on': True,
                         'tools.staticdir.dir': MEDIA_DIR},
              }
    #    #start webservice
    certfile = os.path.join(os.environ['HOME'], 'certinfo')
    if os.path.exists(certfile):
        cherrypy.log('Loading cert info: %s' % certfile)
        cherrypy.config.update(json.load(open(certfile)))
    else:
        cherrypy.log('Cert info unavailable')
    cherrypy.engine.subscribe('start', open_page)
    cherrypy.tree.mount(BIPS(), '/', config=config)
    cherrypy.engine.start()
    cherrypy.engine.block()
    #cherrypy.quickstart(BIPS())
