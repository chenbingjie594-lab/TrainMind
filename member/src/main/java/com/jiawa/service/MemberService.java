package com.jiawa.service;

import com.jiawa.resp.MemberLoginResp;
import com.jiawa.req.MemberLoginReq;
import com.jiawa.req.MemberRegisterReq;
import com.jiawa.req.MemberSendCodeReq;
import jakarta.validation.Valid;

public interface MemberService {
    Integer count();

    long register(MemberRegisterReq memberRegisterReq);

    void sendCode(@Valid MemberSendCodeReq req);

    MemberLoginResp login(@Valid MemberLoginReq req);
}
