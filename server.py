from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/IoT_H2')
def hello_H2():
    return "Hello,IoT_H2"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
