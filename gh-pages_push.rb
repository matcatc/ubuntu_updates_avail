#!/usr/bin/ruby1.8
# uses grancher to push autogenerated docs from the current branch to gh-pages. Thus automatically pushing to the website.
#
require 'grancher'
grancher = Grancher.new do |g|
  g.branch = 'gh-pages'
  g.push_to = 'origin'

  g.message = "pushing autogenerated doc files to gh-pages"
  
  # copy over docbook and doxygen directories
  g.directory 'doc/docbook', 'docbook'
  g.directory 'doc/doxygen', 'doxygen'

  # put the index file in the root directory
  g.file 'doc/index.html', 'index.html'

  # all other files (including those added to gh-pages manually) will be deleted.
end

puts "Commiting"
grancher.commit

# should be able to Ctrl-c in emergency if push is undesired
puts "Pushing"
grancher.push

