ShortCharacterIntroMod = RegisterMod("Short Character Intro", 1)
local mod = ShortCharacterIntroMod

------ Mod Config Menu ------
local json = require("json")

mod.config = {
    toggleKey = Keyboard.KEY_HOME,
}

if ModConfigMenu then
    ModConfigMenu.AddSetting("Short Character Intro", nil,
        {
            Type = ModConfigMenu.OptionType.KEYBIND_KEYBOARD,
            CurrentSetting = function()
                return mod.config.toggleKey
            end,
            Display = function()
                local key = "None"
                if (InputHelper.KeyboardToString[mod.config.toggleKey]) then
                    key = InputHelper.KeyboardToString[mod.config.toggleKey]
                end
                return "Toggle Key: " .. key
            end,
            OnChange = function(currentNum)
                mod.config.toggleKey = currentNum or -1
            end,
            PopupGfx = ModConfigMenu.PopupGfx.WIDE_SMALL,
            PopupWidth = 280,
            Popup = function()
                local currentValue = mod.config.toggleKey
                local keepSettingString = ""
                if currentValue > -1 then
                    local currentSettingString = InputHelper.KeyboardToString[currentValue]
                    keepSettingString = 'Current key: "' .. currentSettingString .. 
                        '".$newlinePress this key again to keep it.$newline$newline'
                end
                return "Press any key to set as toggle key.$newline$newline" ..
                    keepSettingString .. "Press ESCAPE to clear this setting."
            end,
            Info = "Set the key to call the intro animation."
        }
    )
end

mod:AddPriorityCallback(
    ModCallbacks.MC_POST_GAME_STARTED, CallbackPriority.IMPORTANT,
    ---@param isContinued boolean
    function(_, isContinued)
        if not mod:HasData() then
            return
        end

        local jsonString = mod:LoadData()
        mod.config = json.decode(jsonString)
        mod.config.toggleKey = mod.config.toggleKey or Keyboard.KEY_HOME
    end
)

mod:AddPriorityCallback(
    ModCallbacks.MC_PRE_GAME_EXIT, CallbackPriority.LATE,
    function(shouldSave)
        local jsonString = json.encode(mod.config)
        mod:SaveData(jsonString)
    end
)


------ 구현 ------
local sprite = Sprite()
local function LoadSprite()
    local player = Isaac.GetPlayer(0)
    if player:GetPlayerType() < 41 then
        sprite:Load("kr/popup_character descriptions.anm2")    -- 일반 캐릭터
    else
        sprite:Load("kr/popup_workshop descriptions.anm2")    -- 모드 캐릭터
    end
end

mod:AddCallback(ModCallbacks.MC_POST_PLAYER_INIT, LoadSprite)

mod.currentAnim = nil      -- 현재 재생중인 애니메이션 이름
mod.isAnimating = false    -- 애니메이션이 재생 중인지
mod.showIn = true          -- 토글 상태: true면 다음은 인 애니메이션, false면 아웃 애니메이션

mod:AddCallback(ModCallbacks.MC_POST_RENDER, function()
    local player = Isaac.GetPlayer(0)

    if not sprite:IsLoaded() then
        LoadSprite()
    end

    if mod.currentAnim then
        if not sprite:IsFinished(mod.currentAnim) then    -- 애니메이션이 아직 끝나지 않았다면 업데이트
            sprite:Update()
        else
            mod.isAnimating = false
        end

        local scale = 0.75
        if Options.MaxScale == 1 or Options.MaxScale == 2 then
            scale = 0.5
        elseif Options.MaxScale == 3 then
            scale = 0.666666
        end
        
        sprite.Scale = Vector(scale, scale)
        sprite.Color = Color(1, 1, 1, 1, 0, 0, 0)
        
        local room = Game():GetRoom()
        local pos = room:WorldToScreenPosition(Vector(0,0)) - room:GetRenderScrollOffset() - Game().ScreenShakeOffset
        local rx = pos.X + 60 * 26 / 40
        local ry = pos.Y + 162.5 * (26 / 40)
        local screenSize = Vector(rx*2 + 13*26, ry*2 + 7*26)
        sprite:Render(Vector(screenSize.X / 1.98, screenSize.Y / 3.333333), Vector(0,0), Vector(0,0))
    end

    if Input.IsButtonTriggered(mod.config.toggleKey, 0) then
        if mod.isAnimating then return end    -- 만약 애니메이션이 재생 중이면 새 입력은 무시

        local suffix = mod.showIn and "_In" or "_Out"
        local playsfx = mod.showIn and 17 or 18

        if player:GetPlayerType() > 40 then    -- 모드 캐릭터라면
            if FiendFolio and player:GetPlayerType() == FiendFolio.PLAYER.BIEND then    -- 더럽혀진 핀드와 핀드의 이름이 동일하므로
                mod.currentAnim = "CUSTOM_Biend" .. suffix
            else
                mod.currentAnim = "CUSTOM_" .. player:GetName() .. suffix
            end
        else
            mod.currentAnim = player:GetPlayerType() .. suffix
        end

        if Epiphany and player:GetName() == "[TECHNICAL] C-Side Detect" then return end    -- 에피파니 전용 캐릭터 화면은 제외
        if mod.currentAnim then
            sprite:Play(mod.currentAnim, false)
            SFXManager():Play(playsfx, 0.5)
        end
        
        mod.isAnimating = true
        mod.showIn = not mod.showIn
    end
end)
