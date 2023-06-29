#!/usr/bin/python

import socket
import os
from os import environ
import sys
import subprocess

def handleClient(requestSocket):
  # make sure we handle any and all errors that might arise during our exchange with the client
  # simply to ensure that we clean-up correctly -- could me more sophisticated but it does the job
  try:
    socketFile = requestSocket.makefile()
    
    # process the request message
    initialLine = socketFile.readline().strip()
    (method, resource, version) = initialLine.split(' ')
    data = ""
    if resource.find('?') != -1:
      (resource, data) = resource.split('?')
    
    # put in a leading . to indicate that we need to start at the current directory...
    resource = '.' + resource
    
    # if we have a directory, add in index.html to the resource name
    if os.path.isdir(resource):
      resource += "/index.html"

    
    # parse the message headers by reading lines *until* we get to the blank line
    # to simplify, I'm only going to extract the cookie and content length lines
    headerLine = socketFile.readline().strip()
    while len(headerLine) > 0:
      if headerLine.startswith("Cookie"):
        (name, cookies) = headerLine.split(":")
        environ['HTTP_COOKIE'] = cookies.strip()
        
      # only need the content length if we have a POST method
      if method == 'POST' and headerLine.startswith("Content-Length"):
        (name, length) = headerLine.split(":")
        environ['CONTENT_LENGTH'] = length.strip()

      headerLine = socketFile.readline().strip()
    
    
    # prepare the data, via the message body or query string
    if method == 'POST':
      # IMPORTANT: the browser only sends content-length amount of data (no newline) so you have to read an *exact* amount
      data = socketFile.read(int(length))
    else:
      environ['QUERY_STRING'] = data
    
    
    # send the result, if we have a resource
    if os.path.isfile(resource):
      socketFile.write("HTTP/1.1 200 OK\n")
      
      # need to run the resource if it's a .cgi
      if resource.endswith(".cgi"):
        # default to a known value for other method types
        cgiOutput = "Content-Type: text/html\n\n"
        if method == 'POST':
          cgiScript = subprocess.Popen(resource, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
          (cgiOutput,errOutput) = cgiScript.communicate(input=data)
        elif method == 'GET':
          cgiOutput = subprocess.check_output(resource)
          
        # send the output to our client
        socketFile.write(cgiOutput)
      
      else:
        socketFile.write("Content-Type: text/html\n")
        socketFile.write("\n")
        
        # send the resource contents out the socket
        if method != 'HEAD':
          with open( resource, "r" ) as resourceFile:
            socketFile.write(resourceFile.read())
        
    else:
      socketFile.write("HTTP/1.1 404 Not Found\n")
      socketFile.write("Content-Type: text/html\n")
      socketFile.write("\n")
      if method != 'HEAD':
        socketFile.write("Sorry, you can't access that page!\n")

  finally:
    # done, we can clean-up and wait for the next request to come in
    environ['HTTP_COOKIE'] = ""
    environ['CONTENT_LENGTH'] = ""
    environ['QUERY_STRING'] = ""
    socketFile.close()

if __name__ == "__main__":
  done = False

  HOST = ''
  PORT = 15000
  address = (HOST, PORT)

  mySocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  try:
    mySocket.bind(address)
    mySocket.listen(socket.SOMAXCONN)
  except socket.error as e:
    print "unable to bind with '{0}'".format(e.strerror)
    mySocket.close()
    done = True

  # block waiting for a connection, doing this until accept() fails...
  # in the real world you should use a signal to terminate the process
  while not done:
    # this is where we block, so it will be here where we see the kill
    # or do I need to be more cautious (less fine grained)?
    try:
      (requestSocket, clientAddr) = mySocket.accept()

      # if we all had 3430 this is where we'd have a thread pool for handling the clients
      handleClient(requestSocket)
      
      # note that it takes the OS a bit of time (~60s) to cleanup *this* socket (and associated file)
      # if you exit the server right after handling a response an immediate restart will fail (at bind)
      requestSocket.close()

    # any error in the accept() means we're done -- probably due to a ctrl-C
    # not the best solution but it gets the job done here
    # with proper signal handlers (see 3430) this wouldn't be necessary
    except:
      print "\ntime to quit..."
      mySocket.close()
      done = True