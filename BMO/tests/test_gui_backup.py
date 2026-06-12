# test_gui.py


from ui.bmo_face import BMOFace

gui = BMOFace()

# 키 입력 테스트
gui.root.bind("1", lambda event: gui.set_state("sleep"))
gui.root.bind("2", lambda event: gui.set_state("wake"))
gui.root.bind("3", lambda event: gui.set_state("think"))
gui.root.bind("4", lambda event: gui.set_state("happy"))
gui.root.bind("5", lambda event: gui.set_state("sad"))
gui.root.bind("6", lambda event: gui.set_state("angry"))

# 시작 화면
gui.set_state("sleep")

gui.run()
