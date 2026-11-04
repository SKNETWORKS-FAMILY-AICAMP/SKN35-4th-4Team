// ─────────────────────────────────────────────
// 로그인 · 회원가입 화면 (두 화면이 같은 모양이라 한 파일로)
// form 의 data-mode 가 "login" 이면 로그인, "signup" 이면 회원가입
// ─────────────────────────────────────────────
const form = document.getElementById("auth-form");
const input = document.getElementById("user-id");
const button = form.querySelector("button[type=submit]");
const message = document.getElementById("message");

const isSignup = form.dataset.mode === "signup";
const label = button.textContent;                       // "로그인" 또는 "가입하기"

form.addEventListener("submit", async (event) => {
    event.preventDefault();                             // 페이지 새로고침 막고 JS 가 직접 보냄

    showMessage(message, "");
    button.disabled = true;                             // 처리 중: 두 번 누르기 방지
    button.textContent = isSignup ? "가입 중..." : "확인 중...";

    // 1) 프론트 → 백엔드: 아이디를 보냄
    const data = await callApi(isSignup ? API.signup : API.login, {
        method: "POST",
        body: { user_id: input.value.trim() },
    });

    // 2) 답장에 따라 화면을 바꿈
    if (data.ok) {
        showMessage(message, isSignup ? "가입됐어요! 채팅 화면으로 이동합니다." : "로그인됐어요.", true);
        setTimeout(() => { window.location.href = PAGE.chat; }, isSignup ? 800 : 200);
        return;                                         // 이동할 거라 버튼은 잠근 채로
    }

    showMessage(message, data.error || (isSignup ? "가입하지 못했어요." : "로그인하지 못했어요."));
    button.disabled = false;
    button.textContent = label;
});
