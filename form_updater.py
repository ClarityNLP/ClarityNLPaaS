template = '''
    <!doctype html>
    <html lang="en">
    <head>
    <style>
    /* Sticky footer styles
-------------------------------------------------- */
html {
  position: relative;
  min-height: 100%%;
}
body {
  margin-bottom: 60px; /* Margin bottom by footer height */
}




.footer {
  position: absolute;
  bottom: 0;
  width: 100%%;
  height: 60px; /* Set the fixed height of the footer here */
  line-height: 60px; /* Vertically center the text there */
  background-color: #f5f5f5;
}


/* Custom page CSS
-------------------------------------------------- */
/* Not required for template or sticky footer method. */

.container {
  width: auto;
  max-width: 680px;
  padding: 0 15px;
}
</style>    
        <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <meta name="description" content="">
    <meta name="author" content="">
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.1.3/css/bootstrap.min.css" integrity="sha384-MCw98/SFnGE8fJT3GXwEOngsV7Zt27NXFoaoApmYm81iuXoPkFOJwJ8ERdknLPMO" crossorigin="anonymous">
<script src="https://stackpath.bootstrapcdn.com/bootstrap/4.1.3/js/bootstrap.min.js" integrity="sha384-ChfqqxuZUCnJSK3+MXmPNIyE6ZbWh2IMqE241rYiqJxyMiZ6OW/JmZQ5stwEULTy" crossorigin="anonymous"></script>
    <title>ClarityNLPaaS Utilities</title>
    </head>
    <body>
    <main role="main" class="container">
    <br>
    <h1>%s</h1>
    %s
    </main>
       <footer class="footer">
      <div class="container">
        <span class="text-muted">
        <a href="/">Home</a> |
        <a href="https://github.com/ClarityNLP">ClarityNLP Source</a> | 
        <a href="https://claritynlp.readthedocs.io/en/latest/">ClarityNLP Docs</a>
        </span>
      </div>
    </footer>
    </body>
    </html>
    '''

radio_template = '''
  <input type="radio" id="{}" name="slug" value="{}">
  <label for="{}">{}</label><br>
'''

def update_form(slug, form_content):
	print('update {}'.format(slug))
	error = True

	if not error:
		return "{} updated successfully!".format(slug)
	else:
		return "{} failed to update!".format(slug)
