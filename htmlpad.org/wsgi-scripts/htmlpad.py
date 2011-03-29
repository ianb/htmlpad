import os
import re
import httplib
import mimetypes

# TODO: I think it's actually possible to create illegal URLs with this regexp, like
# /foo/rev.34/edit, which is impossible.
pad_re = re.compile(r'^/(?P<name>[A-Za-z\-0-9]+)(?P<ext>\.(css|js|html|txt))?(/rev\.(?P<rev>[0-9]+))?(?P<edit>/edit)?(?P<trailing_slash>|/)?$')

pad_text_url = "/ep/pad/export/%s/latest?format=txt"
pad_rev_text_url = "/ep/pad/export/%s/rev.%d?format=txt"

template_cache = {}

def get_template(name):
    if name not in template_cache:
        tdir = os.path.join(os.path.dirname(__file__), '..', 'templates')
        tfile = open(os.path.join(tdir, name), 'r')
        template_cache[name] = tfile.read()
        tfile.close()
    return template_cache[name]

def application(environ, start_response):
    pad_server = environ['htmlpad.etherpad']
    path = environ['PATH_INFO']
    if path == '/':
        start_response('200 OK', [('Content-Type', 'text/html; charset=utf-8')])
        ## ianb: % is the worst template ever ;)
        ## if you like minimal, you might like Tempita
        ## OTOH, I also find Jinja2 to also be perfectly fine, and other Mozillaers use it; some setup code:
        ## https://github.com/mozilla/openwebapps-directory/blob/master/directory/wsgiapp.py#L38-44
        ## https://github.com/mozilla/openwebapps-directory/blob/master/directory/wsgiapp.py#L100-117
        ## w/o a decent template language you'll probably have XSS holes and other problems
        return get_template('index.html') % {'hostname': environ['HTTP_HOST']}
    if path == '/jquery.js':
        start_response('302 Moved Temporarily',
                       [('Location', 'static-files/jquery.js')])
        return []
    match = pad_re.match(path)
    if match is None:
        start_response('404 Not Found',
                       [('Content-Type', 'text/plain')])
        return ['Not Found']
    padname = match.group('name')
    has_trailing_slash = match.group('trailing_slash')
    ext = match.group('ext')
    urlpath = pad_text_url % padname
    edit_pad_url = "http://%s/%s" % (pad_server, padname)
    if match.group('rev') is not None:
        urlpath = pad_rev_text_url % (padname,
                                      int(match.group('rev')))
    elif match.group('edit') is not None:
        ## ianb: btw you can do dict(name=padname, edit_pad_url=edit_pad_url, ...)
        edit_page = get_template('edit.html') % {
            'name': padname,
            'edit_pad_url': edit_pad_url,
            'view_pad_url': '/%s/' % padname,
            'hostname': environ['HTTP_HOST']
        }
        start_response('200 OK', [('Content-Type', 'text/html; charset=utf-8')])
        return [edit_page]
    elif ext is None and not has_trailing_slash:
        ## ianb: webob.exc.HTTPFound(add_slash=True)
        start_response('302 Found', [('Location', '%s/' % path)])
        return []
    ## ianb: this is where you can actually take a WebOb request, rewrite a few variables to make it point
    ## to your etherpad server, then use wsgiproxy.exactproxy.proxy_exact_request to forward it on
    ## (at least I think you are looking to do something like that)
    ## this does something roughly like that:
    ## https://github.com/mozilla/appetizer-proxyhacks/blob/master/proxyhack/wsgiapp.py#L112-118
    conn = httplib.HTTPConnection(pad_server)
    conn.request("GET", urlpath)
    resp = conn.getresponse()
    if resp.status == 200:
        if ext is not None:
            mimetype = mimetypes.types_map[ext]
        else:
            mimetype = 'text/html'

        mimetype = '%s; charset=utf-8' % mimetype
        start_response('200 OK', [('Content-Type', mimetype)])
        return [resp.read()]
    else:
        failtext = get_template('404.html') % {
          'name': padname,
          'pad_url': '/%s/edit' % padname,
          'hostname': environ['HTTP_HOST']
        }
        # Add some padding so Google Chrome doesn't override our
        # 404 with its own.
        failtext += (" " * 512)
        start_response('404 Not Found',
                       [('Content-Type', 'text/html')])
        return [failtext]
