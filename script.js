
document.addEventListener('DOMContentLoaded', function () {
    const modeToggle = document.getElementById('modeToggle');
    const body = document.body;
    const predefinedQuestions = document.querySelectorAll('#predefinedQuestions li');
    const userQuestion = document.getElementById('userQuestion');

    modeToggle.addEventListener('change', function () {
        if (modeToggle.checked) {
            body.classList.remove('dark-mode');
            body.classList.add('light-mode');
        } else {
            body.classList.remove('light-mode');
            body.classList.add('dark-mode');
        }
    });

    predefinedQuestions.forEach(function(question) {
        question.addEventListener('click', function () {
            userQuestion.value = this.textContent;
        });
    });
});


