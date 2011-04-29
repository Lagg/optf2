import template

class about:
    def GET(self):
        return template.template.about()
