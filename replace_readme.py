import shutil

# Replace README.md with our new version
shutil.copy("README.md.new", "README.md")

# Replace acb/README.md with our new version
shutil.copy("acb/README.md.new", "acb/README.md")

print("README files replaced successfully!")
