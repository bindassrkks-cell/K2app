with open('app/src/main/res/navigation/nav_graph.xml', 'r') as f:
    text = f.read()

text = text.replace('<dialog\n        android:id="@+id/resultCardDetailsDialog"', '<fragment\n        android:id="@+id/resultCardDetailsDialog"')

with open('app/src/main/res/navigation/nav_graph.xml', 'w') as f:
    f.write(text)
