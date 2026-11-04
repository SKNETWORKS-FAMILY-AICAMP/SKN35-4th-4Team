// ─────────────────────────────────────────────
// 로그인 · 회원가입 화면 (두 화면이 같은 모양이라 한 파일로)
// form 의 data-mode 가 "login" 이면 로그인, "signup" 이면 회원가입
// 아이디: 한글 · 영문 · 숫자 · _ 2~20자 (3차와 같음) · 비밀번호: 6~64자
// 백엔드도 같은 규칙으로 한 번 더 검사함
// ─────────────────────────────────────────────
const form = document.getElementById("auth-form");
const input = document.getElementById("user-id");
const password = document.getElementById("password");
const confirmBox = document.getElementById("password-confirm");     // 회원가입 화면에만 있음
const button = form.querySelector("button[type=submit]");
const message = document.getElementById("message");

const isSignup = form.dataset.mode === "signup";
const label = button.textContent;
const RULE = /^[0-9A-Za-z가-힣_]{2,20}$/;

form.addEventListener("submit", async (event) => {
    event.preventDefault();                             // 페이지 새로고침 막고 JS 가 직접 보냄

    const userId = input.value.trim();
    const body = { user_id: userId, password: password.value };
    if (isSignup) {
        if (!RULE.test(userId)) return showMessage(message, "아이디는 한글 · 영문 · 숫자 · _ 로 2~20자예요.");
        if (password.value.length < 6) return showMessage(message, "비밀번호는 6자 이상으로 정해 주세요.");
        if (password.value !== confirmBox.value) {
            confirmBox.focus();
            return showMessage(message, "비밀번호 확인이 맞지 않아요.");
        }
        body.password_confirm = confirmBox.value;
    }

    showMessage(message, "");
    button.disabled = true;
    button.textContent = isSignup ? "만드는 중..." : "확인 중...";

    const data = await callApi(isSignup ? API.signup : API.login, { method: "POST", body });

    if (data.ok) {
        showMessage(message, isSignup ? "아이디를 만들었어요. 바로 시작할게요." : "로그인했어요.", true);
        setTimeout(() => { window.location.href = PAGE.chat; }, isSignup ? 700 : 200);
        return;
    }
    showMessage(message, data.error || (isSignup ? "아이디를 만들지 못했어요." : "로그인하지 못했어요."));
    if (!isSignup) { password.value = ""; password.focus(); }   // 틀리면 비밀번호만 다시
    button.disabled = false;
    button.textContent = label;
});
