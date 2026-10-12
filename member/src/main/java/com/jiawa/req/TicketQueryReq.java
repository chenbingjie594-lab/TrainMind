package com.jiawa.req;

import lombok.Data;

@Data
public class TicketQueryReq extends PageReq {
    private Long memberId;
}
